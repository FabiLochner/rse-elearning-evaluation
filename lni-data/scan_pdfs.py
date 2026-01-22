from pathlib import Path

ROOT_DIR = Path("/Volumes/Archiv/Publikationen/LNI/Proceedings")

def has_metadata_xlsx(folder: Path) -> str | None:
    """
    Prüft, ob im Ordner eine Datei 'metadata-*.xlsx' existiert.
    Gibt den Dateinamen zurück oder None.
    """
    for item in folder.iterdir():
        if (
            item.is_file()
            and item.suffix.lower() == ".xlsx"
            and item.name.lower().startswith("metadata-")
        ):
            return item.name
    return None


def main():
    print(f"Starte Scan in: {ROOT_DIR}")

    if not ROOT_DIR.exists():
        print("❌ Pfad existiert nicht!")
        return

    if not ROOT_DIR.is_dir():
        print("❌ Pfad ist kein Ordner!")
        return

    print("✅ Pfad OK\n")

    proceedings_folders = [p for p in ROOT_DIR.iterdir() if p.is_dir()]
    print(f"Gefundene Proceedings-Ordner: {len(proceedings_folders)}\n")

    total_pdfs = 0
    folders_with_metadata = 0
    folders_without_metadata = 0

    for idx, proc_folder in enumerate(proceedings_folders, start=1):
        print(f"[{idx}/{len(proceedings_folders)}] Scanne: {proc_folder.name}")

        pdfs_in_folder = 0

        for item in proc_folder.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                pdfs_in_folder += 1

        print(f"    → PDFs gefunden: {pdfs_in_folder}")
        total_pdfs += pdfs_in_folder

        # 🔹 vereinfachter Metadaten-Check
        metadata_file = has_metadata_xlsx(proc_folder)

        if metadata_file:
            print(f"    → Metadaten: ✅ {metadata_file}")
            folders_with_metadata += 1
        else:
            print("    → Metadaten: ❌ keine metadata-*.xlsx gefunden")
            folders_without_metadata += 1

    print("\n----- Ergebnis -----")
    print(f"Proceedings-Ordner gescannt: {len(proceedings_folders)}")
    print(f"PDF-Dateien gesamt: {total_pdfs}")
    print(f"Ordner mit Metadaten: {folders_with_metadata}")
    print(f"Ordner ohne Metadaten: {folders_without_metadata}")

if __name__ == "__main__":
    main()
