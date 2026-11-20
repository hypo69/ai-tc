# 🦈 TShark Packet Inspection & Traffic Analysis

Пакет `apps/tshark` предоставляет унифицированную обертку над системной утилитой Wireshark TShark (`tshark.exe`), эвристический анализатор протоколов и интеллектуальный детектор сетевых аномалий для ai-tc.

---

## 📋 Основные компоненты

1. **`TSharkWrapper`** — поиск исполняемого файла TShark в операционной системе, получение списка сетевых интерфейсов (`tshark -D`), чтение и разбор файлов дампов `.pcap` / `.pcapng`, а также потоковый живой захват трафика.
2. **`TrafficAnalyzer`** — расчет агрегированной статистики трафика (объем, число пакетов, распределение протоколов, топ узлов) и эвристический аудит угроз (сканирование портов, открытые незашифрованные протоколы, DNS-всплески).
3. **`AIDetector`** — классификатор сетевых инцидентов и вычисление индекса безопасности сети (`health_score`).
4. **Модели данных (`models.py`)** — Pydantic-модели `PacketSummary`, `NetworkInterface`, `CaptureFilter`, `TrafficStats`, `AnomalyReport`.

---

## 🚀 Примеры использования

```python
from apps.tshark import TSharkWrapper, TrafficAnalyzer, AIDetector

wrapper = TSharkWrapper()
if wrapper.is_available():
    interfaces = wrapper.list_interfaces()
    print(f"Доступно интерфейсов: {len(interfaces)}")

analyzer = TrafficAnalyzer()
packets = wrapper.read_pcap("dump.pcap", max_packets=200)
stats = analyzer.compute_stats(packets)
heuristics = analyzer.detect_heuristics(packets)
```
