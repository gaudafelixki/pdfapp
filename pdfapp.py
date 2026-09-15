import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="PDF & Koordinaten Aktualisierer", layout="wide")
st.title("PDF-Geometrie & Datums-Aktualisierer (für gedruckte PDFs)")

st.write("""
Diese Anwendung durchsucht gedruckte PDFs nach Punktnummern aus der Koordinatendatei
sowie nach Datumsangaben und ersetzt diese präzise an der exakten Originalposition.
""")

# --- 1. Datei-Uploads ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    uploaded_txt = st.file_uploader("1. Koordinatendatei (.txt) hochladen", type=["txt"])
with col_u2:
    uploaded_pdf = st.file_uploader("2. Gedruckte PDF-Datei hochladen", type=["pdf"])

st.divider()

# --- 2. Datumsangaben ---
st.subheader("Datumsfelder aktualisieren")
col_d1, col_d2, col_d3 = st.columns(3)

with col_d1:
    altes_datum = st.text_input("Gesuchtes altes Datum (im PDF)", "01.01.2023", help="Das Datum, das momentan in der PDF steht.")
with col_d2:
    neues_datum_messung = st.text_input("Neues Messdatum", "14.09.2026")
with col_d3:
    neues_datum_auswertung = st.text_input("Neues Auswertungsdatum (Optional)", "")

# Option zur Datums-Unterscheidung falls 2 Daten existieren
such_auswertung_label = st.text_input("Kennzeichnung für 2. Datum (z.B. 'Auswertung:')", "Auswertung:")

st.divider()

def parse_txt_coordinates(txt_file):
    """
    Liest die TXT-Datei ein.
    Erwartetes Format (flexibel):
    Punktnummer  Rechtswert(X)  Hochwert(Y)  [Höhe(Z)]
    Beispiel:
    101  32456123.45  5812345.67  42.10
    """
    coords = {}
    content = txt_file.read().decode("utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            p_nr = parts[0]
            # Formatiert die Koordinaten z.B. tabellarisch oder durch Leerzeichen getrennt
            rest_coord = "  ".join(parts[1:])
            coords[p_nr] = rest_coord
    return coords

def replace_text_exact(page, rect, text, fontsize=9):
    """
    Entfernt den alten Text an der Rechteck-Position präzise
    und fügt den neuen Text dort ein.
    """
    # 1. Weiße Abdeckung über den alten Text legen
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions()
    
    # 2. Neuen Text an der vorherigen Baseline-Höhe schreiben
    # y1 ist der untere Rand des Rechtecks; wir setzen den Text leicht darüber an
    insert_point = fitz.Point(rect.x0, rect.y1 - 1.5)
    page.insert_text(insert_point, text, fontsize=fontsize, fontname="helv", color=(0, 0, 0))

# --- Processing Button ---
if st.button("PDF verarbeiten", type="primary"):
    if not uploaded_txt or not uploaded_pdf:
        st.error("Bitte lade sowohl die TXT-Koordinatendatei als auch die PDF-Datei hoch.")
    else:
        koordinaten_map = parse_txt_coordinates(uploaded_txt)
        pdf_bytes = uploaded_pdf.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        gefundene_punkte = 0
        datum_ersetzungen = 0

        for page in doc:
            # ----------------------------------------------------
            # A) DATUMS-ERSETZUNG
            # ----------------------------------------------------
            if altes_datum:
                date_matches = page.search_for(altes_datum)
                for rect in date_matches:
                    # Prüfen, ob in der Nähe "Auswertung" steht (für das 2. Datum)
                    if neues_datum_auswertung and such_auswertung_label:
                        # Suchbereich leicht erweitern nach links
                        search_area = fitz.Rect(rect.x0 - 150, rect.y0 - 5, rect.x0, rect.y1 + 5)
                        context_text = page.get_text("text", clip=search_area)
                        
                        if such_auswertung_label.lower() in context_text.lower():
                            replace_text_exact(page, rect, neues_datum_auswertung)
                        else:
                            replace_text_exact(page, rect, neues_datum_messung)
                    else:
                        replace_text_exact(page, rect, neues_datum_messung)
                    
                    datum_ersetzungen += 1

            # ----------------------------------------------------
            # B) KOORDINATEN-ERSETZUNG
            # ----------------------------------------------------
            # In gedruckten PDFs liegen Texte oft in Blöcken/Zeilen.
            # Wir holen uns alle Text-Zeilen mit ihrer genauen Position.
            text_instances = page.get_text("words")  # [x0, y0, x1, y1, word, block_no, line_no, word_no]
            
            for p_nr, neue_koordinaten in koordinaten_map.items():
                # Suche nach der Punktnummer
                matches = page.search_for(p_nr)
                for rect in matches:
                    # Suche nach Koordinatenfeldern rechts neben der Punktnummer (gleiche Zeile/Höhe)
                    # Toleranzbereich definieren: gleiche Höhe (y0, y1) und rechts davon (x1 bis x1 + 300)
                    line_rect = fitz.Rect(rect.x1 + 2, rect.y0 - 2, rect.x1 + 350, rect.y1 + 2)
                    
                    # Wenn Koordinatentext in diesem Bereich existiert:
                    existing_coord_text = page.get_text("text", clip=line_rect).strip()
                    
                    if existing_coord_text:
                        # Alten Koordinatenbereich überdecken und neuen Wert schreiben
                        replace_text_exact(page, line_rect, neue_koordinaten)
                        gefundene_punkte += 1

        # Ergebnis-PDF erzeugen
        output_pdf_bytes = doc.write()
        doc.close()

        st.success(f"Verarbeitung abgeschlossen! {gefundene_punkte} Koordinateneinträge und {datum_ersetzungen} Datumsfelder wurden aktualisiert.")

        st.download_button(
            label="Aktualisierte PDF herunterladen",
            data=output_pdf_bytes,
            file_name="aktualisiert_vermessung.pdf",
            mime="application/pdf"
        )