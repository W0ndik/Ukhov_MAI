import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = PROJECT_ROOT / "data" / "exports" / "project-export.json"
IMAGES_DIR = PROJECT_ROOT / "data" / "images"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "assets"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

LABEL_COLORS = {
    "Yellow rust area": (255, 193, 7),
    "Healthy wheat / normal canopy": (76, 175, 80),
    "Bare soil / ground": (158, 158, 158),
    "Unclear / shadow / blur": (156, 39, 176),
}


def get_all_images():
    return [
        path for path in IMAGES_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def normalize_name(value):
    value = str(value)
    value = unquote(value)

    parsed = urlparse(value)
    if parsed.path:
        value = parsed.path

    return Path(value).name


def get_image_value(task):
    data = task.get("data", {})

    # Сначала пробуем стандартные имена полей
    for key in ("image", "img", "undefined", "undefined$"):
        value = data.get(key)
        if value:
            return value

    # Потом ищем любое поле, похожее на изображение
    for value in data.values():
        if not isinstance(value, str):
            continue

        lower_value = value.lower()
        if any(ext in lower_value for ext in IMAGE_EXTENSIONS):
            return value

    return None


def find_image_path(image_value, all_images):
    if not image_value:
        return None

    export_name = normalize_name(image_value)
    export_name_lower = export_name.lower()

    # 1. Точное совпадение имени
    for image_path in all_images:
        if image_path.name.lower() == export_name_lower:
            return image_path

    # 2. Label Studio иногда добавляет префикс к имени файла.
    # Например: abcd1234-DJI_0090.JPG
    # Поэтому ищем, входит ли локальное имя в имя из экспорта.
    for image_path in all_images:
        local_name_lower = image_path.name.lower()
        if local_name_lower in export_name_lower:
            return image_path

    # 3. Обратная проверка: имя из экспорта входит в локальное имя
    for image_path in all_images:
        local_name_lower = image_path.name.lower()
        if export_name_lower in local_name_lower:
            return image_path

    # 4. Пробуем сравнение без части до первого дефиса
    # Например: 123abc-DJI_0090.JPG -> DJI_0090.JPG
    if "-" in export_name:
        short_name = export_name.split("-", 1)[1].lower()
        for image_path in all_images:
            if image_path.name.lower() == short_name:
                return image_path

    return None


def get_results(task):
    results = []

    for annotation in task.get("annotations", []):
        results.extend(annotation.get("result", []))

    # На случай старых версий Label Studio
    for completion in task.get("completions", []):
        results.extend(completion.get("result", []))

    return results


def draw_label(draw, x1, y1, text, color):
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    text_bbox = draw.textbbox((x1, y1), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    label_y1 = max(0, y1 - text_h - 8)
    label_y2 = y1

    draw.rectangle(
        [x1, label_y1, x1 + text_w + 8, label_y2],
        fill=color
    )

    draw.text(
        (x1 + 4, label_y1 + 2),
        text,
        fill=(0, 0, 0),
        font=font
    )


def main():
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(f"Не найден экспорт Label Studio: {EXPORT_PATH}")

    if not IMAGES_DIR.exists():
        raise FileNotFoundError(f"Не найдена папка с изображениями: {IMAGES_DIR}")

    with EXPORT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    all_images = get_all_images()

    if not all_images:
        raise FileNotFoundError(f"В папке {IMAGES_DIR} не найдено изображений")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    skipped_no_image = 0
    skipped_no_match = 0
    skipped_no_boxes = 0

    print(f"Найдено изображений в data/images: {len(all_images)}")
    print(f"Найдено задач в экспорте: {len(data)}")

    for task in data:
        if saved >= 3:
            break

        image_value = get_image_value(task)
        if not image_value:
            skipped_no_image += 1
            continue

        image_path = find_image_path(image_value, all_images)
        if image_path is None:
            skipped_no_match += 1
            print(f"Не найден файл для значения из экспорта: {image_value}")
            continue

        rectangle_results = [
            item for item in get_results(task)
            if item.get("type") == "rectanglelabels"
        ]

        if not rectangle_results:
            skipped_no_boxes += 1
            continue

        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        draw = ImageDraw.Draw(image)

        for item in rectangle_results:
            value = item.get("value", {})
            labels = value.get("rectanglelabels", [])

            if not labels:
                continue

            label = labels[0]
            color = LABEL_COLORS.get(label, (255, 0, 0))

            x = value.get("x", 0) / 100 * width
            y = value.get("y", 0) / 100 * height
            w = value.get("width", 0) / 100 * width
            h = value.get("height", 0) / 100 * height

            x1 = int(x)
            y1 = int(y)
            x2 = int(x + w)
            y2 = int(y + h)

            line_width = max(3, width // 350)

            draw.rectangle(
                [x1, y1, x2, y2],
                outline=color,
                width=line_width
            )

            draw_label(draw, x1, y1, label, color)

        output_path = OUTPUT_DIR / f"example_{saved + 1:02d}.png"
        image.save(output_path)

        print(f"Сохранено: {output_path}")
        saved += 1

    print()
    print("Итог:")
    print(f"Создано визуализаций: {saved}")
    print(f"Пропущено без поля изображения: {skipped_no_image}")
    print(f"Пропущено из-за несовпадения имени файла: {skipped_no_match}")
    print(f"Пропущено без прямоугольных областей: {skipped_no_boxes}")

    if saved == 0:
        print()
        print("Визуализации не созданы.")
        print("Скорее всего, имена файлов в экспорте Label Studio отличаются от имён в data/images.")
        print("Посмотри строки выше: там будут напечатаны значения из экспорта, для которых не найден файл.")


if __name__ == "__main__":
    main()