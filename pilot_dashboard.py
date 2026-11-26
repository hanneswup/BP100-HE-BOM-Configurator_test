"""Power-BI-inspired visuals for historical aggregate pilot metrics."""
import math

import altair as alt
import pandas as pd


def historical_performance_chart(evaluation):
    """Build a two-metric chart; missing or invalid metrics are not shown as zero."""
    rows = []
    for label, key in [('Component precision', 'precision'), ('Component completeness', 'recall')]:
        value = evaluation.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1:
            rows.append({'Metric': label, 'Percent': value * 100, 'Display': f'{value:.1%}'})
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    base = alt.Chart(frame).encode(
        y=alt.Y('Metric:N', sort=['Component precision', 'Component completeness'], title=None,
                axis=alt.Axis(labelFontSize=12, labelColor='#385469', labelLimit=190, ticks=False, domain=False)),
        x=alt.X('Percent:Q', scale=alt.Scale(domain=[0, 100]), title=None,
                axis=alt.Axis(values=[0, 25, 50, 75, 100], labelExpr="datum.value + '%'", grid=True,
                              gridColor='#E8EFF1', domain=False, ticks=False)),
    )
    bars = base.mark_bar(size=24, cornerRadiusEnd=3, color='#28509A').encode(
        tooltip=[alt.Tooltip('Metric:N', title='Historical metric'),
                 alt.Tooltip('Percent:Q', title='Historical value (%)', format='.1f')])
    labels = base.transform_filter('datum.Percent >= 15').mark_text(align='right', dx=-6, color='white', fontWeight='bold', fontSize=12).encode(text='Display:N')
    small_labels = base.transform_filter('datum.Percent < 15').mark_text(align='left', dx=5, color='#15394D', fontWeight='bold', fontSize=12).encode(text='Display:N')
    target = alt.Chart(pd.DataFrame([{'Target': 90}])).mark_rule(color='#D49C26', strokeWidth=3, strokeDash=[5, 3]).encode(
        x=alt.X('Target:Q', scale=alt.Scale(domain=[0, 100]), title=None),
        tooltip=[alt.Tooltip('Target:Q', title='Proposed target (%)')])
    return (bars + labels + small_labels + target).properties(height=115).configure_view(stroke=None)
