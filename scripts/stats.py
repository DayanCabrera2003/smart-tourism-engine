import json

from src.config import settings

def main():
    processed_file = settings.DATA_DIR / "processed" / "destinations.jsonl"
    
    if not processed_file.exists():
        print(f"Error: No se encuentra el archivo {processed_file}")
        return

    destinations = []
    with open(processed_file, "r", encoding="utf-8") as f:
        for line in f:
            destinations.append(json.loads(line))

    total = len(destinations)
    countries = {}
    desc_lengths = []

    for d in destinations:
        country = d.get("country", "Unknown")
        countries[country] = countries.get(country, 0) + 1
        desc_lengths.append(len(d.get("description", "")))

    avg_desc = sum(desc_lengths) / total if total > 0 else 0

    print("--- Estadísticas del Corpus ---")
    print(f"Total de destinos: {total}")
    print(f"Países: {countries}")
    print(f"Longitud media descripción: {avg_desc:.2f} caracteres")
    print("-------------------------------")

if __name__ == "__main__":
    main()
