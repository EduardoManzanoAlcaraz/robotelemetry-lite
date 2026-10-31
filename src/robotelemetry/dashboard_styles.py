"""Estilos de presentación del dashboard, sin recursos ni dependencias externas."""

STYLES = """
<style>
.rt-eyebrow {
    color: inherit; opacity: .72; font-size: .72rem; font-weight: 750;
    letter-spacing: .16em; margin: .3rem 0 .1rem;
}
.rt-brand {
    display: flex; align-items: center; gap: .7rem;
    font-size: 1.05rem; font-weight: 750; margin-bottom: 1.3rem;
}
.rt-brand-mark {
    display: inline-grid; place-items: center; width: 2.3rem; height: 2.3rem;
    border-radius: .7rem; background: #2563eb; color: white; font-size: .9rem;
}
.rt-pill {
    display: inline-block; border-radius: 999px; padding: .23rem .65rem;
    font-size: .75rem; line-height: 1.5; font-weight: 650;
    border: 1px solid transparent;
}
.rt-pill--ok { color: #166534; background: #dcfce7; border-color: #bbf7d0; }
.rt-pill--warning { color: #92400e; background: #fef3c7; border-color: #fde68a; }
.rt-pill--critical { color: #991b1b; background: #fee2e2; border-color: #fecaca; }
.rt-pill--info { color: #1e40af; background: #dbeafe; border-color: #bfdbfe; }
.rt-pill--neutral { color: #475569; background: #f1f5f9; border-color: #e2e8f0; }
.st-key-metric-battery_pct, .st-key-metric-temperature_c,
.st-key-metric-speed_m_s, .st-key-metric-obstacle_distance_m {
    min-height: 10rem; border-radius: .8rem;
}
.st-key-metric-battery_pct { border-top: 3px solid #22c55e; }
.st-key-metric-temperature_c { border-top: 3px solid #f59e0b; }
.st-key-metric-speed_m_s { border-top: 3px solid #3b82f6; }
.st-key-metric-obstacle_distance_m { border-top: 3px solid #8b5cf6; }
.rt-incident-list {
    border: 1px solid rgba(100,116,139,.25); border-radius: .8rem;
    padding: 0 1rem;
}
.rt-incident {
    display: flex; justify-content: space-between; align-items: center;
    gap: 1rem; padding: .9rem 0;
}
.rt-incident + .rt-incident { border-top: 1px solid rgba(100,116,139,.16); }
.rt-incident-title { font-weight: 650; margin-right: .65rem; }
.rt-incident-meta { color: inherit; opacity: .72; font-size: .78rem; margin-top: .3rem; }
.rt-incident-value { text-align: right; white-space: nowrap; font-weight: 650; }
.rt-incident-value small { display: block; font-size: .76rem; font-weight: 400; opacity: .72; }
.rt-footer { color: inherit; opacity: .72; font-size: .76rem; margin-top: 1.5rem; }
@media (max-width: 640px) {
    .rt-incident { align-items: flex-start; }
    .rt-incident-title { display: block; margin-bottom: .3rem; }
}
</style>
"""
