import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = PROJECT_ROOT / "data" / "exports" / "project-export.json"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "annotation_stats.md"


def extract_rectangle_label(result_item):
    labels = result_item.get("value", {}).get("rectanglelabels", [])
    if labels:
        return labels[0]
    return None


def main():
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(f"Не найден экспорт Label Studio: {EXPORT_PATH}")

    with EXPORT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    total_tasks = len(data)
    annotated_tasks = 0
    total_boxes = 0
    class_counter = Counter()

    boxes_per_task = []

    for task in data:
        task_boxes = 0
        annotations = task.get("annotations", [])

        for annotation in annotations:
            results = annotation.get("result", [])

            for item in results:
                if item.get("type") != "rectanglelabels":
                    continue

                label = extract_rectangle_label(item)
                if label is None:
                    continue

                class_counter[label] += 1
                total_boxes += 1
                task_boxes += 1

        if task_boxes > 0:
            annotated_tasks += 1

        boxes_per_task.append(task_boxes)

    avg_boxes = total_boxes / annotated_tasks if annotated_tasks else 0

    lines = []
    lines.append("# Статистика разметки\n")
    lines.append("Статистика рассчитана автоматически по JSON-экспорту Label Studio.\n")
    lines.append("## Общие показатели\n")
    lines.append("| Показатель | Значение |")
    lines.append("|---|---:|")
    lines.append(f"| Всего импортированных изображений | {total_tasks} |")
    lines.append(f"| Изображений с разметкой | {annotated_tasks} |")
    lines.append(f"| Всего прямоугольных областей | {total_boxes} |")
    lines.append(f"| Среднее число областей на размеченное изображение | {avg_boxes:.2f} |")
    lines.append(f"| Количество классов | {len(class_counter)} |")
    lines.append("")

    lines.append("## Распределение по классам\n")
    lines.append("| Класс | Количество областей |")
    lines.append("|---|---:|")

    for label, count in class_counter.most_common():
        lines.append(f"| {label} | {count} |")

    lines.append("")
    lines.append("## Вывод\n")
    lines.append(
        "Разметка содержит прямоугольные области для задачи object detection. "
        "Полученный экспорт может использоваться для последующей подготовки обучающей выборки, "
        "анализа распределения классов и подключения ML-backend для автоматической предразметки."
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Готово: {OUTPUT_PATH}")
    print(f"Всего изображений: {total_tasks}")
    print(f"Размечено изображений: {annotated_tasks}")
    print(f"Всего bbox: {total_boxes}")
    print("Классы:")
    for label, count in class_counter.most_common():
        print(f"  {label}: {count}")


if __name__ == "__main__":
    main()