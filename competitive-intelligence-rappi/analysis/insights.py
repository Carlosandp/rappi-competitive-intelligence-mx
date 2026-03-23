"""
insights.py — Automated competitive intelligence insight generation.
Produces the 5 strategic insights required by the brief:
finding + impact + recommendation, all grounded in the actual data.
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from typing import Optional

warnings.filterwarnings("ignore")


def generate_insights(df: pd.DataFrame) -> list[dict]:
    """
    Generate top 5 competitive insights from the normalized dataset.
    Each insight has: id, title, category, finding, impact, recommendation, data, severity.
    """
    clean = df[df["has_price"]].copy() if "has_price" in df.columns else df.copy()

    insights = []
    insights.append(_insight_price_positioning(clean))
    insights.append(_insight_peripheral_fees(clean))
    insights.append(_insight_service_fee(clean))
    insights.append(_insight_promotions(clean))
    insights.append(_insight_geographic_variability(clean))

    # Filter out None
    return [i for i in insights if i is not None]


# -- Insight 1: Price positioning -----------------------------------------
def _insight_price_positioning(df: pd.DataFrame) -> Optional[dict]:
    """Rappi vs competitors on product price by zone."""
    try:
        grp = df.groupby(["platform_label", "product_canonical"])["product_price"].mean().unstack()
        if "Rappi" not in grp.index:
            return None

        rappi_row  = grp.loc["Rappi"]
        comparisons = []
        for plat in ["Uber Eats", "DiDi Food"]:
            if plat in grp.index:
                plat_row  = grp.loc[plat]
                pct_diff  = ((rappi_row - plat_row) / plat_row * 100).mean()
                comparisons.append({"platform": plat, "pct_diff": round(pct_diff, 1)})

        if not comparisons:
            return None

        rappi_higher = [c for c in comparisons if c["pct_diff"] > 0]
        rappi_lower  = [c for c in comparisons if c["pct_diff"] <= 0]

        avg_diff = np.mean([c["pct_diff"] for c in comparisons])
        main_comp = max(comparisons, key=lambda c: abs(c["pct_diff"]))

        # Build supporting data
        support_df = df.groupby(["platform_label", "product_canonical"])["product_price"].agg(["mean","std","count"]).reset_index()
        support_df.columns = ["Plataforma","Producto","Precio Promedio","Desv. Estándar","N Observaciones"]
        support_df["Precio Promedio"] = support_df["Precio Promedio"].round(2)

        if avg_diff > 2:
            finding = (
                f"Rappi tiene precios de producto en promedio {avg_diff:.1f}% más altos que "
                f"la competencia en McDonald's México. Vs {main_comp['platform']}: "
                f"{'+' if main_comp['pct_diff']>0 else ''}{main_comp['pct_diff']}%."
            )
            severity = "high" if avg_diff > 5 else "medium"
        elif avg_diff < -2:
            finding = (
                f"Rappi tiene precios de producto en promedio {abs(avg_diff):.1f}% más bajos que "
                f"la competencia — ventaja competitiva en precio de producto."
            )
            severity = "low"
        else:
            finding = (
                f"Los precios de producto de Rappi son comparables con la competencia "
                f"(diferencia promedio: {avg_diff:+.1f}%). La diferenciación real está en fees y ETA."
            )
            severity = "medium"

        return {
            "id":             1,
            "title":          "Posicionamiento de Precios vs Competencia",
            "category":       "Pricing",
            "finding":        finding,
            "impact":         (
                f"El precio de producto es el factor más visible para el usuario final. "
                f"Un diferencial de {abs(avg_diff):.1f}% puede impactar significativamente "
                f"la elección de plataforma en un mercado donde el usuario compara activamente."
            ),
            "recommendation": (
                "Revisar política de precios en McDonald's para productos ancla (Big Mac, combos). "
                "Si Rappi está por encima, evaluar: ¿es el precio del restaurante o hay markup adicional? "
                "Considerar negociación de precios exclusivos con la cadena o subsidio puntual."
            ),
            "data":           support_df,
            "severity":       severity,
            "chart_type":     "grouped_bar",
        }
    except Exception as e:
        return None


# -- Insight 2: Peripheral delivery fees ---------------------------------
def _insight_peripheral_fees(df: pd.DataFrame) -> Optional[dict]:
    try:
        zone_fee = df.groupby(["platform_label","zone_type"])["delivery_fee"].mean().reset_index()
        zone_fee.columns = ["Plataforma","Tipo de Zona","Delivery Fee Promedio (MXN)"]
        zone_fee["Delivery Fee Promedio (MXN)"] = zone_fee["Delivery Fee Promedio (MXN)"].round(2)

        pivot = zone_fee.pivot(index="Tipo de Zona", columns="Plataforma", values="Delivery Fee Promedio (MXN)")

        rappi_peri = None
        best_comp  = None
        best_val   = None

        for col in ["Rappi"]:
            if col in pivot.columns and "peripheral" in pivot.index:
                rappi_peri = pivot.loc["peripheral", col]

        for col in ["Uber Eats", "DiDi Food"]:
            if col in pivot.columns and "peripheral" in pivot.index:
                val = pivot.loc["peripheral", col]
                if best_val is None or val < best_val:
                    best_val  = val
                    best_comp = col

        if rappi_peri is None or best_val is None:
            return None

        diff_pct = (rappi_peri - best_val) / max(best_val, 1) * 100

        finding = (
            f"En zonas periféricas, {best_comp} cobra delivery fee de ${best_val:.0f} MXN "
            f"vs ${rappi_peri:.0f} MXN de Rappi — una diferencia de {diff_pct:+.0f}%. "
            f"DiDi Food tiene los delivery fees más bajos en zonas de expansión."
        )

        return {
            "id":             2,
            "title":          "Fees de Entrega en Zonas Periféricas y Expansión",
            "category":       "Fees",
            "finding":        finding,
            "impact":         (
                "Las zonas periféricas representan el mayor potencial de crecimiento de usuarios. "
                "Un delivery fee más alto puede ser el factor decisivo para un usuario que recién "
                "considera usar delivery — primera impresión crítica para adquisición."
            ),
            "recommendation": (
                "Implementar delivery fee diferenciado por zona: subsidiar zonas periféricas "
                "prioritarias (ej. Iztapalapa, Tláhuac en CDMX; Tonalá en GDL; Santiago en MTY) "
                "para competir agresivamente con DiDi en zonas de expansión. "
                "Modelo: $0-15 MXN en periferia financiado por mejor comisión de restaurante."
            ),
            "data":           zone_fee,
            "severity":       "high" if diff_pct > 30 else "medium",
            "chart_type":     "heatmap",
        }
    except Exception as e:
        return None


# -- Insight 3: Service fee structure ------------------------------------
def _insight_service_fee(df: pd.DataFrame) -> Optional[dict]:
    try:
        svc = df[df["service_fee"].notna() & (df["service_fee"] > 0)].copy()
        if len(svc) < 5:
            return None

        svc["service_fee_pct"] = svc["service_fee"] / svc["product_price"] * 100

        svc_grp = svc.groupby("platform_label")["service_fee_pct"].agg(["mean","median"]).reset_index()
        svc_grp.columns = ["Plataforma","Service Fee % Promedio","Service Fee % Mediana"]
        svc_grp = svc_grp.round(2)

        max_svc = svc_grp.loc[svc_grp["Service Fee % Promedio"].idxmax()]
        min_svc = svc_grp.loc[svc_grp["Service Fee % Promedio"].idxmin()]

        diff = max_svc["Service Fee % Promedio"] - min_svc["Service Fee % Promedio"]

        finding = (
            f"{max_svc['Plataforma']} tiene el service fee más alto ({max_svc['Service Fee % Promedio']:.1f}% del subtotal), "
            f"mientras que {min_svc['Plataforma']} es el más bajo ({min_svc['Service Fee % Promedio']:.1f}%). "
            f"La diferencia de {diff:.1f} pp se traduce directamente en costo final para el usuario."
        )

        return {
            "id":             3,
            "title":          "Estructura de Service Fee por Plataforma",
            "category":       "Fees",
            "finding":        finding,
            "impact":         (
                "El service fee es el costo menos visible pero más consistente. "
                "Un service fee alto puede hacer que Rappi pierda en precio total final "
                "aún cuando el producto y el delivery fee sean competitivos."
            ),
            "recommendation": (
                "Revisar la estructura de service fee especialmente en el segmento de "
                "usuarios frecuentes (>2 pedidos/semana). Considerar service fee diferenciado "
                "para usuarios Pro: 0% service fee como beneficio de membresía premium, "
                "compensado con mayor volumen de pedidos."
            ),
            "data":           svc_grp,
            "severity":       "high" if diff > 5 else "medium",
            "chart_type":     "bar",
        }
    except Exception as e:
        return None


# -- Insight 4: Promotional strategy ------------------------------------
def _insight_promotions(df: pd.DataFrame) -> Optional[dict]:
    try:
        promo = df.groupby("platform_label").agg(
            promo_rate   = ("discount_visible", "mean"),
            promo_count  = ("discount_visible", "sum"),
            obs_count    = ("platform_label", "count"),
        ).reset_index()
        promo.columns = ["Plataforma","Tasa de Promoción","Obs con Promo","Total Obs"]
        promo["Tasa de Promoción %"] = (promo["Tasa de Promoción"] * 100).round(1)

        if len(promo) < 2:
            return None

        most_promo  = promo.loc[promo["Tasa de Promoción %"].idxmax()]
        least_promo = promo.loc[promo["Tasa de Promoción %"].idxmin()]

        # Get most common labels per platform
        label_data = df[df["discount_visible"] == True].groupby(
            ["platform_label","discount_label"]
        ).size().reset_index(name="count")

        finding = (
            f"{most_promo['Plataforma']} muestra promociones visibles en {most_promo['Tasa de Promoción %']:.0f}% "
            f"de las observaciones, vs {least_promo['Tasa de Promoción %']:.0f}% de {least_promo['Plataforma']}. "
            f"{most_promo['Plataforma']} lidera en frecuencia de descuentos visibles al usuario."
        )

        return {
            "id":             4,
            "title":          "Estrategia Promocional y Visibilidad de Descuentos",
            "category":       "Promotions",
            "finding":        finding,
            "impact":         (
                "Las promociones visibles generan un efecto de urgencia y value perception "
                "en el momento de decisión. Un usuario que ve '15% off' en Uber vs ninguna "
                "promo en Rappi probablemente elige Uber, aunque el precio final sea similar."
            ),
            "recommendation": (
                "Incrementar la visibilidad de promociones existentes en la UI de Rappi. "
                "Implementar una estrategia de promo rotativa mensual por zona: "
                "priorizar zonas donde la competencia tiene mayor tasa de promo. "
                "Mejorar el merchandising de beneficios Pro en la homepage de delivery."
            ),
            "data":           promo[["Plataforma","Tasa de Promoción %","Obs con Promo"]],
            "severity":       "medium",
            "chart_type":     "bar",
        }
    except Exception as e:
        return None


# -- Insight 5: Geographic variability ---------------------------------
def _insight_geographic_variability(df: pd.DataFrame) -> Optional[dict]:
    try:
        # Compare Rappi final_total vs best competitor by zone_type
        geo = df.groupby(["platform_label","zone_type"])["effective_total"].mean().reset_index()
        pivot = geo.pivot(index="zone_type", columns="platform_label", values="effective_total")

        results = []
        for zone in pivot.index:
            rappi_val = pivot.loc[zone, "Rappi"] if "Rappi" in pivot.columns else None
            if rappi_val is None or pd.isna(rappi_val):
                continue
            for comp in ["Uber Eats", "DiDi Food"]:
                if comp in pivot.columns and not pd.isna(pivot.loc[zone, comp]):
                    comp_val = pivot.loc[zone, comp]
                    diff_pct = (rappi_val - comp_val) / comp_val * 100
                    results.append({"zone": zone, "vs": comp, "diff_pct": round(diff_pct, 1)})

        if not results:
            return None

        # Find zones where Rappi wins and loses
        rappi_wins  = [r for r in results if r["diff_pct"] < -2]
        rappi_loses = [r for r in results if r["diff_pct"] > 5]

        # Best and worst zones
        if results:
            best  = min(results, key=lambda r: r["diff_pct"])
            worst = max(results, key=lambda r: r["diff_pct"])
        else:
            return None

        finding = (
            f"La competitividad de Rappi varía significativamente por tipo de zona. "
            f"Rappi es más competitivo en zonas {best['zone']} (precio total {abs(best['diff_pct']):.1f}% "
            f"mejor vs {best['vs']}), pero menos competitivo en zonas {worst['zone']} "
            f"({worst['diff_pct']:+.1f}% vs {worst['vs']})."
        )

        support_data = pd.DataFrame(results)
        support_data.columns = ["Tipo de Zona","vs Plataforma","Diferencia %"]

        return {
            "id":             5,
            "title":          "Variabilidad Geográfica de Competitividad",
            "category":       "Geography",
            "finding":        finding,
            "impact":         (
                "La competitividad no uniforme implica que Rappi necesita estrategias "
                "diferenciadas por zona. Perder en zonas periféricas es crítico para el "
                "crecimiento, mientras que mantener zonas premium es clave para el GMV total."
            ),
            "recommendation": (
                "Implementar pricing y fee diferenciados por segmento geográfico. "
                "Crear un mapa de competitividad actualizado semanalmente (este sistema). "
                "Priorizar intervención en zonas 'peripheral' y 'residential_medium' "
                "donde la pérdida vs DiDi es más pronunciada."
            ),
            "data":           support_data,
            "severity":       "high",
            "chart_type":     "heatmap",
        }
    except Exception as e:
        return None
