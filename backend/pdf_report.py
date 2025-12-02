"""
PDF Report Generator for FaithTracker Management Reports
Uses WeasyPrint to generate professional PDF reports from HTML templates
"""

from weasyprint import HTML
from datetime import datetime
from typing import Dict, Any


def generate_monthly_report_pdf(report_data: Dict[str, Any], campus_name: str = "GKBJ") -> bytes:
    """
    Generate a professional PDF management report from report data.

    Args:
        report_data: The monthly report data from get_monthly_management_report()
        campus_name: Name of the church/campus

    Returns:
        PDF content as bytes
    """

    # Extract data sections
    period = report_data.get("report_period", {})
    exec_summary = report_data.get("executive_summary", {})
    kpis = report_data.get("kpis", {})
    ministry = report_data.get("ministry_highlights", {})
    care_breakdown = report_data.get("care_breakdown", [])
    insights = report_data.get("insights", [])
    recommendations = report_data.get("recommendations", [])
    comparison = report_data.get("comparison", {})

    # Format numbers
    def fmt_num(n):
        if n is None:
            return "0"
        if isinstance(n, float):
            return f"{n:,.1f}"
        return f"{n:,}"

    def fmt_currency(n):
        if n is None:
            return "Rp 0"
        return f"Rp {n:,.0f}"

    # Generate care breakdown rows
    care_rows = ""
    for care in care_breakdown:
        care_rows += f"""
        <tr>
            <td>{care.get('label', 'Unknown')}</td>
            <td class="text-center">{care.get('total', 0)}</td>
            <td class="text-center text-success">{care.get('completed', 0)}</td>
            <td class="text-center text-warning">{care.get('pending', 0)}</td>
            <td class="text-center text-muted">{care.get('ignored', 0)}</td>
        </tr>
        """

    # Generate insights
    insights_html = ""
    for insight in insights:
        icon = "✅" if insight.get("type") == "success" else "⚠️" if insight.get("type") == "warning" else "ℹ️"
        color = "#22c55e" if insight.get("type") == "success" else "#f59e0b" if insight.get("type") == "warning" else "#3b82f6"
        insights_html += f"""
        <div class="insight-item" style="border-left: 4px solid {color};">
            <span class="insight-icon">{icon}</span>
            <div>
                <strong>{insight.get('category', '')}</strong>
                <p>{insight.get('message', '')}</p>
            </div>
        </div>
        """

    # Generate recommendations
    recommendations_html = ""
    for i, rec in enumerate(recommendations, 1):
        recommendations_html += f"""
        <div class="recommendation-item">
            <span class="rec-number">{i}</span>
            <p>{rec}</p>
        </div>
        """

    # Birthday KPI data
    bday = kpis.get("birthday_completion_rate", {})
    engagement = kpis.get("member_engagement_rate", {})
    care_rate = kpis.get("care_completion_rate", {})
    reach_rate = kpis.get("member_reach_rate", {})

    # Comparison data
    comp_events = comparison.get("total_events", {})
    comp_completion = comparison.get("completion_rate", {})
    comp_financial = comparison.get("financial_aid", {})

    # Get current date for metadata
    generated_date = datetime.now().strftime('%Y-%m-%d')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="author" content="{campus_name}">
        <meta name="description" content="Monthly Pastoral Care Report for {period.get('month_name', '')} {period.get('year', '')}">
        <meta name="keywords" content="pastoral care, church report, ministry, {campus_name}">
        <meta name="generator" content="FaithTracker Pastoral Care System">
        <meta name="dcterms.created" content="{generated_date}">
        <meta name="dcterms.modified" content="{generated_date}">
        <title>Pastoral Care Report - {campus_name} - {period.get('month_name', '')} {period.get('year', '')}</title>
        <style>
            @page {{
                size: A4;
                margin: 15mm 15mm 20mm 15mm;
                @bottom-center {{
                    content: "Page " counter(page) " of " counter(pages);
                    font-size: 9pt;
                    color: #666;
                }}
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.5;
                color: #1f2937;
            }}

            .header {{
                text-align: center;
                padding-bottom: 15px;
                border-bottom: 3px solid #14b8a6;
                margin-bottom: 20px;
            }}

            .header h1 {{
                font-size: 22pt;
                color: #14b8a6;
                margin-bottom: 5px;
                font-weight: 700;
            }}

            .header h2 {{
                font-size: 14pt;
                color: #374151;
                font-weight: 400;
            }}

            .header .date {{
                font-size: 9pt;
                color: #6b7280;
                margin-top: 8px;
            }}

            .section {{
                margin-bottom: 20px;
                page-break-inside: avoid;
            }}

            .section-title {{
                font-size: 13pt;
                font-weight: 700;
                color: #14b8a6;
                border-bottom: 2px solid #e5e7eb;
                padding-bottom: 5px;
                margin-bottom: 12px;
            }}

            .stats-grid {{
                display: flex;
                flex-wrap: wrap;
                margin-bottom: 15px;
                margin-left: -5px;
                margin-right: -5px;
            }}

            .stat-box {{
                flex: 1;
                min-width: 100px;
                background: #f9fafb;
                border-radius: 8px;
                padding: 12px;
                text-align: center;
                margin: 5px;
            }}

            .stat-box.highlight {{
                background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);
                color: white;
            }}

            .stat-box.success {{
                background: #dcfce7;
            }}

            .stat-box.warning {{
                background: #fef3c7;
            }}

            .stat-box.danger {{
                background: #fee2e2;
            }}

            .stat-value {{
                font-size: 24pt;
                font-weight: 700;
                line-height: 1.2;
            }}

            .stat-label {{
                font-size: 9pt;
                color: #6b7280;
                margin-top: 3px;
            }}

            .stat-box.highlight .stat-label {{
                color: rgba(255,255,255,0.9);
            }}

            .kpi-grid {{
                display: flex;
                flex-wrap: wrap;
                margin-left: -6px;
                margin-right: -6px;
            }}

            .kpi-card {{
                flex: 1;
                min-width: 120px;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 12px;
                margin: 6px;
            }}

            .kpi-title {{
                font-size: 9pt;
                color: #6b7280;
                margin-bottom: 5px;
            }}

            .kpi-value {{
                font-size: 20pt;
                font-weight: 700;
                color: #14b8a6;
            }}

            .kpi-subtitle {{
                font-size: 8pt;
                color: #9ca3af;
                margin-top: 3px;
            }}

            .kpi-target {{
                font-size: 8pt;
                color: #6b7280;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 9pt;
            }}

            th {{
                background: #14b8a6;
                color: white;
                padding: 8px 10px;
                text-align: left;
                font-weight: 600;
            }}

            td {{
                padding: 8px 10px;
                border-bottom: 1px solid #e5e7eb;
            }}

            tr:nth-child(even) {{
                background: #f9fafb;
            }}

            .text-center {{
                text-align: center;
            }}

            .text-success {{
                color: #22c55e;
            }}

            .text-warning {{
                color: #f59e0b;
            }}

            .text-danger {{
                color: #ef4444;
            }}

            .text-muted {{
                color: #9ca3af;
            }}

            .ministry-grid {{
                display: flex;
                flex-wrap: wrap;
                margin-left: -6px;
                margin-right: -6px;
            }}

            .ministry-card {{
                flex: 1;
                min-width: 130px;
                background: #f9fafb;
                border-radius: 8px;
                padding: 12px;
                margin: 6px;
            }}

            .ministry-card h4 {{
                font-size: 9pt;
                color: #6b7280;
                margin-bottom: 5px;
            }}

            .ministry-card .value {{
                font-size: 18pt;
                font-weight: 700;
                color: #374151;
            }}

            .ministry-card .sub {{
                font-size: 8pt;
                color: #9ca3af;
            }}

            .insight-item {{
                display: flex;
                align-items: flex-start;
                padding: 10px;
                background: #f9fafb;
                border-radius: 6px;
                margin-bottom: 8px;
            }}

            .insight-icon {{
                font-size: 14pt;
                margin-right: 10px;
            }}

            .insight-item strong {{
                font-size: 9pt;
                color: #374151;
            }}

            .insight-item p {{
                font-size: 9pt;
                color: #6b7280;
                margin-top: 2px;
            }}

            .recommendation-item {{
                display: flex;
                align-items: flex-start;
                padding: 8px;
                margin-bottom: 6px;
            }}

            .rec-number {{
                background: #14b8a6;
                color: white;
                width: 22px;
                height: 22px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10pt;
                font-weight: 600;
                flex-shrink: 0;
                margin-right: 10px;
            }}

            .recommendation-item p {{
                font-size: 9pt;
                color: #374151;
            }}

            .comparison-grid {{
                display: flex;
                flex-wrap: wrap;
                margin-left: -6px;
                margin-right: -6px;
            }}

            .comparison-card {{
                flex: 1;
                min-width: 100px;
                background: #f9fafb;
                border-radius: 8px;
                padding: 10px;
                text-align: center;
                margin: 6px;
            }}

            .comparison-card .label {{
                font-size: 8pt;
                color: #6b7280;
                margin-bottom: 3px;
            }}

            .comparison-card .current {{
                font-size: 16pt;
                font-weight: 700;
                color: #374151;
            }}

            .comparison-card .change {{
                font-size: 9pt;
                margin-top: 3px;
            }}

            .change-positive {{
                color: #22c55e;
            }}

            .change-negative {{
                color: #ef4444;
            }}

            .footer {{
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #e5e7eb;
                text-align: center;
                font-size: 8pt;
                color: #9ca3af;
            }}

            .two-column {{
                display: flex;
                margin-left: -7px;
                margin-right: -7px;
            }}

            .two-column > div {{
                flex: 1;
                margin: 0 7px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{campus_name}</h1>
            <h2>Monthly Pastoral Care Report</h2>
            <div class="date">
                {period.get('month_name', '')} {period.get('year', '')} |
                Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}
            </div>
        </div>

        <div class="section">
            <div class="section-title">Executive Summary</div>
            <div class="stats-grid">
                <div class="stat-box highlight">
                    <div class="stat-value">{fmt_num(exec_summary.get('total_members', 0))}</div>
                    <div class="stat-label">Total Members</div>
                </div>
                <div class="stat-box success">
                    <div class="stat-value">{fmt_num(exec_summary.get('active_members', 0))}</div>
                    <div class="stat-label">Active</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-value">{fmt_num(exec_summary.get('at_risk_members', 0))}</div>
                    <div class="stat-label">At Risk</div>
                </div>
                <div class="stat-box danger">
                    <div class="stat-value">{fmt_num(exec_summary.get('disconnected_members', 0))}</div>
                    <div class="stat-label">Disconnected</div>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-value">{fmt_num(exec_summary.get('total_care_events', 0))}</div>
                    <div class="stat-label">Care Events</div>
                </div>
                <div class="stat-box success">
                    <div class="stat-value">{fmt_num(exec_summary.get('completed_events', 0))}</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-value">{fmt_num(exec_summary.get('pending_events', 0))}</div>
                    <div class="stat-label">Pending</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{fmt_currency(exec_summary.get('financial_aid_total', 0))}</div>
                    <div class="stat-label">Financial Aid</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Key Performance Indicators</div>
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-title">Care Completion Rate</div>
                    <div class="kpi-value">{fmt_num(care_rate.get('current', 0))}%</div>
                    <div class="kpi-target">Target: {care_rate.get('target', 85)}%</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Member Engagement</div>
                    <div class="kpi-value">{fmt_num(engagement.get('current', 0))}%</div>
                    <div class="kpi-subtitle">{fmt_num(engagement.get('disconnected_percentage', 0))}% disconnected</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Member Reach</div>
                    <div class="kpi-value">{fmt_num(reach_rate.get('current', 0))}%</div>
                    <div class="kpi-subtitle">{reach_rate.get('members_contacted', 0)} contacted</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Birthday Completion</div>
                    <div class="kpi-value">{fmt_num(bday.get('current', 0))}%</div>
                    <div class="kpi-subtitle">{bday.get('celebrated', 0)} of {bday.get('total', 0)}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Ministry Highlights</div>
            <div class="ministry-grid">
                <div class="ministry-card">
                    <h4>Grief Support</h4>
                    <div class="value">{ministry.get('grief_support', {}).get('families_supported', 0)}</div>
                    <div class="sub">families | {ministry.get('grief_support', {}).get('total_touchpoints', 0)} touchpoints</div>
                </div>
                <div class="ministry-card">
                    <h4>Hospital Visits</h4>
                    <div class="value">{ministry.get('hospital_visits', {}).get('total_visits', 0)}</div>
                    <div class="sub">visits | {ministry.get('hospital_visits', {}).get('patients_visited', 0)} patients</div>
                </div>
                <div class="ministry-card">
                    <h4>Birthdays</h4>
                    <div class="value">{ministry.get('birthday_ministry', {}).get('celebrated', 0)}</div>
                    <div class="sub">celebrated | {ministry.get('birthday_ministry', {}).get('ignored', 0)} skipped</div>
                </div>
                <div class="ministry-card">
                    <h4>Financial Aid</h4>
                    <div class="value">{fmt_currency(ministry.get('financial_aid', {}).get('total_amount', 0))}</div>
                    <div class="sub">{ministry.get('financial_aid', {}).get('recipients', 0)} recipients</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Care Events Breakdown</div>
            <table>
                <thead>
                    <tr>
                        <th>Event Type</th>
                        <th class="text-center">Total</th>
                        <th class="text-center">Completed</th>
                        <th class="text-center">Pending</th>
                        <th class="text-center">Ignored</th>
                    </tr>
                </thead>
                <tbody>
                    {care_rows if care_rows else '<tr><td colspan="5" class="text-center text-muted">No care events this period</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <div class="section-title">Month-over-Month Comparison</div>
            <div class="comparison-grid">
                <div class="comparison-card">
                    <div class="label">Total Events</div>
                    <div class="current">{fmt_num(comp_events.get('current', 0))}</div>
                    <div class="change {'change-positive' if comp_events.get('change', 0) >= 0 else 'change-negative'}">
                        {'+' if comp_events.get('change', 0) >= 0 else ''}{fmt_num(comp_events.get('change', 0))} vs last month
                    </div>
                </div>
                <div class="comparison-card">
                    <div class="label">Completion Rate</div>
                    <div class="current">{fmt_num(comp_completion.get('current', 0))}%</div>
                    <div class="change {'change-positive' if comp_completion.get('change', 0) >= 0 else 'change-negative'}">
                        {'+' if comp_completion.get('change', 0) >= 0 else ''}{fmt_num(comp_completion.get('change', 0))}%
                    </div>
                </div>
                <div class="comparison-card">
                    <div class="label">Financial Aid</div>
                    <div class="current">{fmt_currency(comp_financial.get('current', 0))}</div>
                    <div class="change {'change-positive' if comp_financial.get('change', 0) >= 0 else 'change-negative'}">
                        {'+' if comp_financial.get('change', 0) >= 0 else ''}{fmt_currency(comp_financial.get('change', 0))}
                    </div>
                </div>
            </div>
        </div>

        <div class="two-column">
            <div class="section">
                <div class="section-title">Strategic Insights</div>
                {insights_html if insights_html else '<p class="text-muted">No specific insights for this period</p>'}
            </div>

            <div class="section">
                <div class="section-title">Recommendations</div>
                {recommendations_html if recommendations_html else '<p class="text-muted">No specific recommendations</p>'}
            </div>
        </div>

        <div class="footer">
            <p>This report was automatically generated by FaithTracker Pastoral Care System</p>
            <p>For questions, please contact your system administrator</p>
        </div>
    </body>
    </html>
    """

    # Generate PDF - WeasyPrint 60.2 extracts metadata from HTML meta tags automatically
    html = HTML(string=html_content)
    return html.write_pdf()
