"""Build the French PDF report from the model's generated outputs."""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
DATA = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
NAVY = colors.HexColor("#18324B")
BLUE = colors.HexColor("#2F6B8A")
PALE = colors.HexColor("#EAF1F5")
MID = colors.HexColor("#D6E1E8")
TEXT = colors.HexColor("#263746")
MUTED = colors.HexColor("#627484")


def register_fonts():
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("C:/Windows/Fonts/calibri.ttf"), Path("C:/Windows/Fonts/calibrib.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("ReportSans", str(regular)))
            pdfmetrics.registerFont(TTFont("ReportSans-Bold", str(bold)))
            return "ReportSans", "ReportSans-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, BOLD = register_fonts()
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="ReportTitle", fontName=BOLD, fontSize=24, leading=29, textColor=NAVY, spaceAfter=4))
styles.add(ParagraphStyle(name="Subtitle", fontName=FONT, fontSize=11, leading=15, textColor=BLUE, spaceAfter=12))
styles.add(ParagraphStyle(name="Section", fontName=BOLD, fontSize=15, leading=19, textColor=NAVY, spaceBefore=5, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle(name="Subsection", fontName=BOLD, fontSize=11, leading=14, textColor=BLUE, spaceBefore=5, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="BodyReport", fontName=FONT, fontSize=9.5, leading=14, textColor=TEXT, spaceAfter=6))
styles.add(ParagraphStyle(name="SmallReport", fontName=FONT, fontSize=8, leading=11, textColor=MUTED))
styles.add(ParagraphStyle(name="Cell", fontName=FONT, fontSize=8.5, leading=11, textColor=TEXT))
styles.add(ParagraphStyle(name="CellBold", fontName=BOLD, fontSize=8.5, leading=11, textColor=NAVY))
styles.add(ParagraphStyle(name="HeadCell", fontName=BOLD, fontSize=8.5, leading=11, textColor=colors.white))
styles.add(ParagraphStyle(name="KpiValue", fontName=BOLD, fontSize=15, leading=18, textColor=NAVY, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="KpiLabel", fontName=FONT, fontSize=7.5, leading=10, textColor=MUTED, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="Flow", fontName=BOLD, fontSize=8.5, leading=11, textColor=NAVY, alignment=TA_CENTER))


def para(text, style="BodyReport"):
    return Paragraph(text, styles[style])


def frnum(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",")


class FlowDiagram(Flowable):
    def __init__(self, width, height=76):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        labels = [
            "Événements<br/>sismiques",
            "Indice PGA<br/>simulé",
            "Paiement<br/>contractuel",
            "Prix et<br/>mesures de risque",
        ]
        gap = 18
        box_w = (self.width - gap * 3) / 4
        box_h = 43
        y = 20
        for i, label in enumerate(labels):
            x = i * (box_w + gap)
            c.setFillColor(PALE)
            c.setStrokeColor(MID)
            c.roundRect(x, y, box_w, box_h, 5, fill=1, stroke=1)
            p = Paragraph(label, styles["Flow"])
            _, ph = p.wrap(box_w - 8, box_h - 4)
            p.drawOn(c, x + 4, y + (box_h - ph) / 2)
            if i < 3:
                c.setStrokeColor(BLUE)
                c.setLineWidth(1.5)
                sx = x + box_w + 3
                ex = sx + gap - 6
                cy = y + box_h / 2
                c.line(sx, cy, ex, cy)
                c.line(ex - 4, cy + 3, ex, cy)
                c.line(ex - 4, cy - 3, ex, cy)


def image(name, width, max_height):
    path = OUT / name
    im = Image(str(path), width=width, height=max_height, kind="proportional")
    im.hAlign = "CENTER"
    return im


def data_table(rows, widths, header=True):
    if header:
        rows = [[Paragraph(cell.getPlainText(), styles["HeadCell"]) for cell in rows[0]], *rows[1:]]
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.45, MID),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    for row in range(1 if header else 0, len(rows)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F7FAFC")))
    table.setStyle(TableStyle(commands))
    return table


def on_page(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(w - 18 * mm, 10 * mm, f"{doc.page}")
    canvas.restoreState()


def main():
    pdf_path = OUT / "rapport_catastrophe_naturelle.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=17 * mm,
        title="Pricing d'une couverture paramétrique séisme",
        author="Étude de modélisation actuarielle en Python",
    )
    width = A4[0] - 36 * mm
    base = DATA["base"]
    unc = DATA["param_uncertainty"]
    basis = DATA["basis"]
    story = []

    # Page 1: model overview and headline pricing results.
    story += [Spacer(1, 7 * mm), para("Pricing d'une couverture<br/>paramétrique séisme", "ReportTitle"),
              para("Simulation de l'aléa · tarification · basis risk", "Subtitle"),
              para("Cette étude construit une chaîne de pricing indexée sur l'accélération maximale du sol (PGA). Les événements simulés alimentent une structure de paiement contractuelle; les paiements annuels servent ensuite à mesurer prix et risques.")]
    story += [FlowDiagram(width), Spacer(1, 2 * mm), para("Contrat étudié", "Section")]
    contract_rows = [
        [para("PGA", "CellBold"), para("0,08 g", "CellBold"), para("0,15 g", "CellBold"), para("0,25 g", "CellBold")],
        [para("Part de la limite", "Cell"), para("25 %", "Cell"), para("50 %", "Cell"), para("100 %", "Cell")],
    ]
    story += [data_table(contract_rows, [width * .36, width * .21, width * .21, width * .22]), Spacer(1, 4 * mm)]
    kpis = [[para(f"{base['AAL']/1e3:.1f} k$".replace(".", ","), "KpiValue"), para(f"{base['premium_sd']/1e3:.1f} k$".replace(".", ","), "KpiValue"), para(f"{base['prob_trigger']*100:.2f} %".replace(".", ","), "KpiValue"), para(f"{base['ROL_sd']*100:.2f} %".replace(".", ","), "KpiValue")],
            [para("AAL", "KpiLabel"), para("Prime (écart-type)", "KpiLabel"), para("Années avec paiement", "KpiLabel"), para("Rate on line", "KpiLabel")]]
    kt = Table(kpis, colWidths=[width / 4] * 4, hAlign="LEFT")
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), .5, MID), ("INNERGRID", (0, 0), (-1, -1), .5, MID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [kt, Spacer(1, 4 * mm), image("fig1_payout_pga.png", width * .83, 53 * mm),
              para("Figure 1. Fonction de paiement et distribution du PGA simulé.", "SmallReport")]

    # Page 2: annual risk distribution and parameter uncertainty.
    story += [PageBreak(), para("Tarification et incertitude", "ReportTitle"),
              para("La simulation couvre 200 000 années. Chaque année agrège les paiements des événements et applique la limite annuelle de 10 M$.")]
    price_rows = [[para("Indicateur", "CellBold"), para("Résultat", "CellBold"), para("Interprétation", "CellBold")],
                  [para("AAL", "CellBold"), para(f"{base['AAL']:,.0f} $".replace(",", " "), "Cell"), para("Paiement annuel moyen", "Cell")],
                  [para("VaR 99 %", "CellBold"), para(f"{base['VaR99']/1e6:.2f} M$".replace(".", ","), "Cell"), para("Quantile 99 % du paiement annuel", "Cell")],
                  [para("TVaR 99 %", "CellBold"), para(f"{base['TVaR99']/1e6:.2f} M$".replace(".", ","), "Cell"), para("Moyenne des 1 % d'années les plus coûteuses", "Cell")],
                  [para("Prime coût du capital", "CellBold"), para(f"{base['premium_coc']/1e3:.1f} k$".replace(".", ","), "Cell"), para("Variante à 10 % de charge sur TVaR99 − AAL", "Cell")]]
    story += [data_table(price_rows, [width * .25, width * .22, width * .53]), Spacer(1, 3 * mm),
              para("La prime de référence est calculée comme AAL + 0,35 × écart-type des paiements annuels. La TVaR est calculée sur exactement 1 % des observations, ce qui traite correctement les ex æquo de cette distribution discrète.")]
    story += [para("Courbe de dépassement", "Section"), image("fig2_ep_curve.png", width * .78, 58 * mm),
              para("Figure 2. Paiement annuel associé aux périodes de retour simulées.", "SmallReport"),
              para("Incertitude paramétrique", "Section"),
              para(f"Deux cents catalogues pseudo-observés de 60 ans servent à réestimer la fréquence et la b-value, puis à recalculer la prime. La prime moyenne est de {frnum(unc['mean']/1e3)} k$; l'intervalle P5–P95 est {frnum(unc['p5']/1e3)}–{frnum(unc['p95']/1e3)} k$ (coefficient de variation {frnum(unc['cv']*100)} %)."),
              image("fig3_param_uncertainty.png", width * .72, 49 * mm),
              para("Figure 3. Distribution de prime après réestimation des paramètres.", "SmallReport")]

    # Page 3: basis risk and trigger design.
    story += [PageBreak(), para("Basis risk et conception du trigger", "ReportTitle"),
              para("Le basis risk apparaît lorsque l'indice contractuel ne reflète pas exactement la perte économique au portefeuille. Le modèle représente cet écart par une erreur spatiale sur le PGA, puis une fonction de vulnérabilité avec bruit multiplicatif.")]
    basis_rows = [[para("Mesure", "CellBold"), para("Résultat", "CellBold")],
                  [para("Corrélation perte / indemnité", "Cell"), para(f"{basis['corr']:.3f}".replace(".", ","), "Cell")],
                  [para("Paiement sans perte matérielle", "Cell"), para(f"{basis['P(payout & loss immaterial)']*100:.2f} %".replace(".", ","), "Cell")],
                  [para("Perte matérielle sans paiement", "Cell"), para(f"{basis['P(loss material & no payout)']*100:.2f} %".replace(".", ","), "Cell")],
                  [para("RMSE perte / indemnité", "Cell"), para(f"{basis['RMSE']/1e3:.1f} k$".replace(".", ","), "Cell")]]
    story += [data_table(basis_rows, [width * .67, width * .33]), Spacer(1, 3 * mm),
              para("La perte dite matérielle correspond ici à plus de 5 % de la limite, seuil de démonstration choisi pour comparer les erreurs de déclenchement.") ,
              para("Seuil de déclenchement", "Section"),
              para("Pour une couverture binaire, le relèvement du seuil réduit la fréquence des paiements et le coût du contrat, mais augmente les pertes matérielles sans indemnité. Sur la grille testée, les deux fréquences d'erreur changent d'ordre entre 0,12 g et 0,16 g; le point d'égalité n'est pas estimé plus finement."),
              image("fig4_trigger_frontier.png", width * .95, 70 * mm),
              para("Figure 4. Prime et erreurs de déclenchement selon le seuil PGA.", "SmallReport")]

    # Page 4: sensitivities and limitations.
    story += [PageBreak(), para("Sensibilités et limites", "ReportTitle"),
              para("Les sensibilités modifient une hypothèse à la fois autour du scénario de référence. Elles quantifient la dépendance du résultat aux paramètres du modèle; ce ne sont pas des intervalles de confiance.") ,
              image("fig5_sensitivity.png", width * .82, 75 * mm),
              para("Figure 5. Variation relative de la prime dans les scénarios étudiés.", "SmallReport")]
    sens_rows = [[para("Hypothèse", "CellBold"), para("Étendue de variation", "CellBold")],
                 [para("Atténuation c2 de la GMPE", "Cell"), para("−22,7 % à +39,2 %", "Cell")],
                 [para("Écart-type σ de la GMPE", "Cell"), para("−16,2 % à +19,2 %", "Cell")],
                 [para("Taux et b-value", "Cell"), para("environ ±13–15 %", "Cell")]]
    story += [data_table(sens_rows, [width * .60, width * .40]), Spacer(1, 5 * mm), para("Conclusion", "Section"),
              para("Dans ce prototype, le choix de la relation d'atténuation du PGA est le principal déterminant du prix. L'analyse met aussi en évidence le compromis entre niveau de trigger, coût et risque de non-indemnisation."),
              para("Limites du modèle", "Section"),
              para("Le catalogue, la GMPE et la vulnérabilité sont stylisés; ils ne sont calibrés ni à une région ni à des données de sinistres réelles. Les résultats sont conditionnels à ces hypothèses et ne représentent pas une cotation de marché. Une application réelle requerrait un catalogue historique, une GMPE publiée pour la zone étudiée et une calibration de la vulnérabilité du portefeuille."),
              Spacer(1, 4 * mm), para("Reproductibilité : graine fixe, sorties générées par run_analysis.py. Les montants sont exprimés en dollars américains.", "SmallReport")]

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(pdf_path)


if __name__ == "__main__":
    main()
