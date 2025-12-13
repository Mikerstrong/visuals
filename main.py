import json
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Budgets (normalized keys)
BUDGETS = {
    "groupa": 50000,
    "groupb": 40000,
    "groupc": 55500,
    "parts": 290000,
}

DATA_PATH = Path(__file__).parent / "sample.json"

@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        st.error(f"Data file not found: {DATA_PATH}")
        return pd.DataFrame(columns=["Part Name", "Group Name", "Date", "Amount"]) 
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    df = pd.DataFrame(raw)
    # Parse dates
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    # Normalize group names for consistent joins
    df["Group Key"] = df["Group Name"].str.strip().str.lower()
    return df


def get_month_bounds(ref_date: date):
    start = date(ref_date.year, ref_date.month, 1)
    # next month
    if ref_date.month == 12:
        next_month_start = date(ref_date.year + 1, 1, 1)
    else:
        next_month_start = date(ref_date.year, ref_date.month + 1, 1)
    return start, next_month_start


def filter_month(df: pd.DataFrame, which: str):
    today = date.today()
    cur_start, cur_next = get_month_bounds(today)
    # previous month
    if cur_start.month == 1:
        prev_start = date(cur_start.year - 1, 12, 1)
    else:
        prev_start = date(cur_start.year, cur_start.month - 1, 1)
    prev_next = cur_start

    if which == "Current Month":
        mask = (df["Date"] >= cur_start) & (df["Date"] < cur_next)
    else:
        mask = (df["Date"] >= prev_start) & (df["Date"] < prev_next)
    out = df.loc[mask].copy()
    out["Day"] = pd.to_datetime(out["Date"]).dt.day
    return out


def build_daily_group_usage(df: pd.DataFrame) -> pd.DataFrame:
    # Sum by day + group
    grouped = (
        df.groupby(["Day", "Group Key", "Group Name"], as_index=False)["Amount"].sum()
        .sort_values(["Day", "Group Key"])
    )
    return grouped


def build_expected_daily(df: pd.DataFrame) -> pd.DataFrame:
    # Expected usage: allocate monthly budget evenly per day up to last day present in filtered df
    if df.empty:
        return pd.DataFrame(columns=["Day", "Group Name", "Expected"])
    last_day = int(df["Day"].max())
    days = list(range(1, last_day + 1))

    records = []
    for gkey, gname in df[["Group Key", "Group Name"]].drop_duplicates().values:
        monthly_budget = BUDGETS.get(gkey, 0)
        daily = monthly_budget / 30.0  # simple equal spread over 30 days
        for d in days:
            records.append({
                "Day": d,
                "Group Name": gname,
                "Expected": daily,
            })
    exp = pd.DataFrame(records)
    return exp


def main():
    st.set_page_config(page_title="Budget Usage Dashboard", layout="wide")
    st.title("Company Parts Budget Usage")
    st.caption("Displays money spent for current/previous month from sample.json")

    df = load_data()

    # Controls
    option = st.selectbox(
        "Select period",
        options=["Current Month", "Previous Month"],
        index=0,
    )

    filtered = filter_month(df, option)

    # Totals
    total_spent = filtered["Amount"].sum() if not filtered.empty else 0.0
    st.subheader(f"Total Spent – {option}")
    st.metric(label="Amount", value=f"${total_spent:,.2f}")

    # Budget comparison by group
    if not filtered.empty:
        st.subheader(f"1. Budget vs Actual – {option}")
        group_spending = filtered.groupby(["Group Key", "Group Name"])["Amount"].sum().reset_index()
        
        comparison_data = []
        for _, row in group_spending.iterrows():
            group_key = row["Group Key"]
            group_name = row["Group Name"]
            actual = row["Amount"]
            budget = BUDGETS.get(group_key, 0)
            variance = actual - budget
            variance_pct = (variance / budget * 100) if budget > 0 else 0
            
            comparison_data.append({
                "Group": group_name,
                "Budget": f"${budget:,.2f}",
                "Actual": f"${actual:,.2f}",
                "Variance": f"${variance:,.2f}",
                "Variance %": f"{variance_pct:+.1f}%"
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, width="stretch")

    st.divider()

    # Show table of current month data by default per requirements
    st.subheader(f"2. Transactions – {option}")
    st.dataframe(filtered.sort_values(["Group Name", "Date"]).reset_index(drop=True))

    # Build charts
    daily_usage = build_daily_group_usage(filtered)
    expected = build_expected_daily(daily_usage)

    st.subheader("3. Daily Usage per Group")
    if daily_usage.empty:
        st.info("No data for the selected month.")
    else:
        # Cumulative Step Line Charts - One for each group
        st.subheader("4. Cumulative Step Line Charts by Group")
        groups = daily_usage["Group Name"].unique()
        
        for group_name in groups:
            group_data = daily_usage[daily_usage["Group Name"] == group_name].copy()
            group_expected = expected[expected["Group Name"] == group_name] if not expected.empty else pd.DataFrame()
            
            # Calculate cumulative spending
            group_data = group_data.sort_values("Day")
            group_data["Cumulative"] = group_data["Amount"].cumsum()
            
            fig_step = go.Figure()
            
            # Cumulative step line for actual spending
            fig_step.add_trace(
                go.Scatter(
                    x=group_data["Day"],
                    y=group_data["Cumulative"],
                    mode="lines",
                    line=dict(shape="hv"),  # horizontal-vertical step
                    name=f"Cumulative Actual - {group_name}",
                    line_color="blue",
                    hovertemplate="Day %{x}<br>Cumulative: $%{y:,.0f}<extra></extra>"
                )
            )
            
            # Cumulative expected line
            if not group_expected.empty:
                group_expected_sorted = group_expected.sort_values("Day")
                group_expected_sorted["Cumulative Expected"] = group_expected_sorted["Expected"].cumsum()
                fig_step.add_trace(
                    go.Scatter(
                        x=group_expected_sorted["Day"],
                        y=group_expected_sorted["Cumulative Expected"],
                        mode="lines",
                        name=f"Cumulative Expected - {group_name}",
                        line=dict(dash="dash", color="red"),
                        hovertemplate="Day %{x}<br>Expected: $%{y:,.0f}<extra></extra>"
                    )
                )
            
            # Add vertical lines for weekly markers (every 7 days)
            week_days = [7, 14, 21, 28]
            for week_day in week_days:
                fig_step.add_vline(
                    x=week_day, 
                    line_dash="dot", 
                    line_color="gray", 
                    opacity=0.5,
                    annotation_text=f"Week {week_day//7}",
                    annotation_position="top"
                )
            
            fig_step.update_layout(
                title=f"Cumulative Daily Spending - {group_name}",
                xaxis_title="Day of Month",
                yaxis_title="Cumulative Amount ($)",
                height=400,
                yaxis_tickformat="$,.0f"
            )
            st.plotly_chart(fig_step, width="stretch")
        
        # Bar Charts - One for each group  
        st.subheader("5. Daily Bar Charts by Group")
        
        for group_name in groups:
            group_data = daily_usage[daily_usage["Group Name"] == group_name]
            group_expected = expected[expected["Group Name"] == group_name] if not expected.empty else pd.DataFrame()
            
            fig_bar = go.Figure()
            
            # Get individual transactions for this group to create stacked segments
            group_transactions = filtered[filtered["Group Name"] == group_name].copy()
            
            # Create stacked bars with each part as a separate segment
            colors = ["blue", "gray", "lightblue", "darkgray", "steelblue", "lightgray"]
            
            # Get unique parts for this group
            unique_parts = group_transactions["Part Name"].unique()
            
            for i, part_name in enumerate(unique_parts):
                part_data = group_transactions[group_transactions["Part Name"] == part_name]
                part_daily = part_data.groupby("Day")["Amount"].sum().reset_index()
                
                color = colors[i % len(colors)]
                fig_bar.add_trace(
                    go.Bar(
                        x=part_daily["Day"],
                        y=part_daily["Amount"],
                        name=part_name,
                        marker_color=color,
                        opacity=0.7,
                        hovertemplate=f"{part_name}<br>Day %{{x}}<br>Amount: $%{{y:,.0f}}<extra></extra>"
                    )
                )
            
            # Expected line overlay
            if not group_expected.empty:
                fig_bar.add_trace(
                    go.Scatter(
                        x=group_expected["Day"],
                        y=group_expected["Expected"],
                        mode="lines",
                        name=f"Expected - {group_name}",
                        line=dict(dash="dash", color="red", width=3),
                        hovertemplate="Day %{x}<br>Expected: $%{y:,.0f}<extra></extra>"
                    )
                )
            
            # Add vertical lines for weekly markers (every 7 days)
            week_days = [7, 14, 21, 28]
            for week_day in week_days:
                fig_bar.add_vline(
                    x=week_day, 
                    line_dash="dot", 
                    line_color="gray", 
                    opacity=0.5,
                    annotation_text=f"Week {week_day//7}",
                    annotation_position="top"
                )
            
            fig_bar.update_layout(
                title=f"Daily Spending Bars - {group_name}",
                xaxis_title="Day of Month",
                yaxis_title="Amount ($)",
                height=400,
                bargap=0.2,
                yaxis_tickformat="$,.0f",
                barmode="stack"
            )
            st.plotly_chart(fig_bar, width="stretch")

        # ===== ADVANCED BUDGET ANALYSIS SECTIONS =====
        
        # 6. Gauge Charts - Budget Utilization
        st.subheader("6. Budget Utilization Gauges")
        cols = st.columns(2)
        for i, group_name in enumerate(groups):
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                actual_month_spending = group_data_single["Amount"].sum()
                monthly_budget = BUDGETS.get(group_key, 1)
                utilization = (actual_month_spending / monthly_budget * 100) if monthly_budget > 0 else 0
                
                # Calculate budget remaining or overspend amount
                budget_difference = monthly_budget - actual_month_spending
                
                # Set delta value and color
                if budget_difference >= 0:
                    delta_color = "green"
                    delta_text = f"${budget_difference:,.0f} remaining"
                else:
                    delta_color = "red"  
                    delta_text = f"${abs(budget_difference):,.0f} over budget"
                
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = utilization,
                    number = {'suffix': "%"},
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': f"{group_name}<br>Monthly Budget vs Spent<br>Budget: ${monthly_budget:,.0f} | Spent: ${actual_month_spending:,.0f}<br><span style='color:{delta_color}'>{delta_text}</span>"},
                    gauge = {
                        'axis': {'range': [None, 120]},  # Extended to show over-budget
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 65], 'color': "lightgreen"},
                            {'range': [65, 80], 'color': "yellow"},
                            {'range': [80, 100], 'color': "red"},
                            {'range': [100, 120], 'color': "darkred"}],
                        'threshold': {
                            'line': {'color': "blue", 'width': 4},
                            'thickness': 0.75,
                            'value': 100}}))
                fig_gauge.update_layout(height=300)
                cols[i % 2].plotly_chart(fig_gauge, width="stretch")

        # 7. Waterfall Chart - Budget to Actual
        st.subheader("7. Budget Waterfall Analysis")
        waterfall_data = []
        running_total = 0
        
        for row in comparison_data:
            group = row["Group"]
            budget = float(row["Budget"].replace("$", "").replace(",", ""))
            actual = float(row["Actual"].replace("$", "").replace(",", ""))
            variance = actual - budget
            
            waterfall_data.extend([
                {"Group": f"{group} Budget", "Amount": budget, "Type": "Budget"},
                {"Group": f"{group} Variance", "Amount": variance, "Type": "Variance"}
            ])
        
        if waterfall_data:
            fig_waterfall = go.Figure()
            x_pos = 0
            colors = []
            
            for item in waterfall_data:
                color = "green" if item["Type"] == "Budget" else ("red" if item["Amount"] > 0 else "blue")
                fig_waterfall.add_trace(go.Bar(
                    x=[x_pos],
                    y=[abs(item["Amount"])],
                    name=item["Group"],
                    marker_color=color,
                    hovertemplate=f"{item['Group']}<br>${item['Amount']:,.0f}<extra></extra>"
                ))
                x_pos += 1
            
            fig_waterfall.update_layout(
                title="Budget vs Actual Waterfall",
                showlegend=False,
                height=400,
                yaxis_tickformat="$,.0f"
            )
            st.plotly_chart(fig_waterfall, width="stretch")

        # 8. Heat Map - Daily Spending Intensity
        st.subheader("8. Daily Spending Heat Map")
        if not filtered.empty:
            # Create pivot table for heatmap
            heatmap_data = filtered.groupby(["Day", "Group Name"])["Amount"].sum().reset_index()
            heatmap_pivot = heatmap_data.pivot(index="Group Name", columns="Day", values="Amount").fillna(0)
            
            fig_heatmap = go.Figure(data=go.Heatmap(
                z=heatmap_pivot.values,
                x=heatmap_pivot.columns,
                y=heatmap_pivot.index,
                colorscale='Blues',
                hovertemplate='Group: %{y}<br>Day: %{x}<br>Amount: $%{z:,.0f}<extra></extra>'
            ))
            
            fig_heatmap.update_layout(
                title="Daily Spending Intensity by Group",
                xaxis_title="Day of Month",
                yaxis_title="Group",
                height=300
            )
            st.plotly_chart(fig_heatmap, width="stretch")

        # 9. Weekly Budget Burn Rate
        st.subheader("9. Weekly Budget Burn Rate")
        if not filtered.empty:
            # Calculate weekly spending
            filtered_copy = filtered.copy()
            filtered_copy["Week"] = ((pd.to_datetime(filtered_copy["Date"]).dt.day - 1) // 7) + 1
            weekly_spending = filtered_copy.groupby(["Week", "Group Name"])["Amount"].sum().reset_index()
            
            fig_weekly = px.bar(
                weekly_spending,
                x="Week",
                y="Amount",
                color="Group Name",
                title="Weekly Spending by Group",
                barmode="group"
            )
            fig_weekly.update_layout(
                yaxis_tickformat="$,.0f",
                height=400
            )
            st.plotly_chart(fig_weekly, width="stretch")

        # 10. Running Variance Analysis  
        st.subheader("10. Cumulative Budget Variance")
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name].copy()
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                budget = BUDGETS.get(group_key, 0)
                daily_budget = budget / 30
                
                group_data_single = group_data_single.sort_values("Day")
                group_data_single["Cumulative_Actual"] = group_data_single["Amount"].cumsum()
                group_data_single["Cumulative_Budget"] = group_data_single["Day"] * daily_budget
                group_data_single["Cumulative_Variance"] = group_data_single["Cumulative_Actual"] - group_data_single["Cumulative_Budget"]
                
                fig_variance = go.Figure()
                fig_variance.add_trace(go.Scatter(
                    x=group_data_single["Day"],
                    y=group_data_single["Cumulative_Variance"],
                    mode="lines+markers",
                    name=f"{group_name} Variance",
                    line=dict(color="red" if group_data_single["Cumulative_Variance"].iloc[-1] > 0 else "green")
                ))
                fig_variance.add_hline(y=0, line_dash="dash", line_color="gray")
                
                fig_variance.update_layout(
                    title=f"Cumulative Variance - {group_name}",
                    xaxis_title="Day of Month",
                    yaxis_title="Variance from Budget ($)",
                    height=400,
                    yaxis_tickformat="$,.0f"
                )
                st.plotly_chart(fig_variance, width="stretch")

        # 11. Budget Progress Bars
        st.subheader("11. Budget Utilization Progress")
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                actual = group_data_single["Amount"].sum()
                budget = BUDGETS.get(group_key, 1)
                percentage = min((actual / budget * 100), 150) if budget > 0 else 0
                
                # Color coding
                if percentage <= 80:
                    color = "normal"
                elif percentage <= 100:
                    color = "warning" 
                else:
                    color = "danger"
                
                st.metric(
                    label=f"{group_name} Budget Usage", 
                    value=f"{percentage:.1f}%",
                    delta=f"${actual - budget:,.0f} vs budget"
                )
                st.progress(min(percentage/100, 1.0))

        # 12. Forecast Projection
        st.subheader("12. Month-End Spending Forecast")
        today_day = 12  # Current day of month
        forecast_data = []
        
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                budget = BUDGETS.get(group_key, 0)
                actual_to_date = group_data_single["Amount"].sum()
                daily_avg = actual_to_date / len(group_data_single)
                days_remaining = 31 - today_day
                projected_total = actual_to_date + (daily_avg * days_remaining)
                
                forecast_data.append({
                    "Group": group_name,
                    "Actual to Date": f"${actual_to_date:,.0f}",
                    "Projected Total": f"${projected_total:,.0f}",
                    "Budget": f"${budget:,.0f}",
                    "Projected Variance": f"${projected_total - budget:,.0f}",
                    "Risk Level": "🔴 High" if projected_total > budget * 1.1 else "🟡 Medium" if projected_total > budget else "🟢 Low"
                })
        
        if forecast_data:
            forecast_df = pd.DataFrame(forecast_data)
            st.dataframe(forecast_df, width="stretch")

        # 13. Variance Rankings
        st.subheader("13. Budget Variance Rankings")
        if comparison_data:
            ranking_data = []
            for row in comparison_data:
                variance_val = float(row["Variance"].replace("$", "").replace(",", ""))
                ranking_data.append({
                    "Rank": 0,
                    "Group": row["Group"],
                    "Variance": row["Variance"],
                    "Variance %": row["Variance %"],
                    "Status": "🔴 Over Budget" if variance_val > 0 else "🟢 Under Budget"
                })
            
            # Sort by absolute variance
            ranking_data.sort(key=lambda x: abs(float(x["Variance"].replace("$", "").replace(",", ""))), reverse=True)
            for i, row in enumerate(ranking_data):
                row["Rank"] = i + 1
            
            ranking_df = pd.DataFrame(ranking_data)
            st.dataframe(ranking_df, width="stretch")

        # 14. Alert Dashboard
        st.subheader("14. Budget Alert Dashboard")
        alert_threshold = st.slider("Alert Threshold (%)", 50, 150, 90)
        
        alerts = []
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                actual = group_data_single["Amount"].sum()
                budget = BUDGETS.get(group_key, 1)
                utilization = (actual / budget * 100) if budget > 0 else 0
                
                if utilization >= alert_threshold:
                    alert_level = "🚨 Critical" if utilization > 100 else "⚠️ Warning"
                    alerts.append({
                        "Group": group_name,
                        "Utilization": f"{utilization:.1f}%",
                        "Amount Over Threshold": f"${actual - (budget * alert_threshold/100):,.0f}",
                        "Alert Level": alert_level
                    })
        
        if alerts:
            alert_df = pd.DataFrame(alerts)
            st.dataframe(alert_df, width="stretch")
        else:
            st.success(f"✅ All groups are within the {alert_threshold}% threshold!")

        # 15. Parts Value Alert Dashboard
        st.subheader("15. Parts Value Alert Dashboard")
        
        # Get min and max part values for slider range
        if not filtered.empty:
            min_amount = int(filtered["Amount"].min())
            max_amount = int(filtered["Amount"].max())
            
            # Slider for parts threshold
            parts_threshold = st.slider(
                "Parts Value Threshold ($)", 
                min_value=min_amount, 
                max_value=max_amount, 
                value=int(max_amount * 0.7),  # Default to 70% of max
                step=100
            )
            
            # Filter parts above threshold
            high_value_parts = filtered[filtered["Amount"] >= parts_threshold].copy()
            
            if not high_value_parts.empty:
                # Sort by amount descending
                high_value_parts = high_value_parts.sort_values("Amount", ascending=False)
                
                # Create alert data
                parts_alerts = []
                for _, row in high_value_parts.iterrows():
                    amount = row["Amount"]
                    alert_level = "🚨 Critical" if amount > max_amount * 0.9 else "⚠️ High Value"
                    
                    parts_alerts.append({
                        "Part Name": row["Part Name"],
                        "Group": row["Group Name"],
                        "Date": row["Date"],
                        "Amount": f"${amount:,.0f}",
                        "Over Threshold": f"${amount - parts_threshold:,.0f}",
                        "Alert Level": alert_level
                    })
                
                # Display summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Parts Above Threshold", len(parts_alerts))
                with col2:
                    total_over_threshold = high_value_parts["Amount"].sum()
                    st.metric("Total Value", f"${total_over_threshold:,.0f}")
                with col3:
                    avg_over_threshold = high_value_parts["Amount"].mean()
                    st.metric("Average Value", f"${avg_over_threshold:,.0f}")
                
                # Display the parts alert table
                parts_alert_df = pd.DataFrame(parts_alerts)
                st.dataframe(parts_alert_df, width="stretch")
                
                # Show distribution by group
                st.subheader("High Value Parts by Group")
                group_dist = high_value_parts.groupby("Group Name").agg({
                    "Amount": ["count", "sum", "mean"]
                }).round(0)
                group_dist.columns = ["Count", "Total ($)", "Average ($)"]
                group_dist = group_dist.reset_index()
                
                # Format currency columns
                group_dist["Total ($)"] = group_dist["Total ($)"].apply(lambda x: f"${x:,.0f}")
                group_dist["Average ($)"] = group_dist["Average ($)"].apply(lambda x: f"${x:,.0f}")
                
                st.dataframe(group_dist, width="stretch")
                
            else:
                st.info(f"💡 No parts found above ${parts_threshold:,} threshold.")
                st.balloons()  # Celebrate when no high-value parts!
        else:
            st.info("No data available for parts analysis.")

        # ===== ADVANCED ANALYTICS SECTIONS =====
        
        # 16. Budget Velocity Dashboard
        st.subheader("16. Budget Velocity Dashboard")
        if not filtered.empty:
            velocity_data = []
            for group_name in groups:
                group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
                if not group_data_single.empty:
                    group_key = group_data_single["Group Key"].iloc[0]
                    budget = BUDGETS.get(group_key, 0)
                    actual = group_data_single["Amount"].sum()
                    days_elapsed = 12  # Current day of month
                    days_in_month = 31
                    
                    actual_velocity = actual / days_elapsed if days_elapsed > 0 else 0
                    expected_velocity = budget / days_in_month
                    velocity_ratio = (actual_velocity / expected_velocity * 100) if expected_velocity > 0 else 0
                    
                    status = "🟢 Optimal" if 80 <= velocity_ratio <= 120 else "🟡 Caution" if 60 <= velocity_ratio <= 140 else "🔴 Critical"
                    
                    velocity_data.append({
                        "Group": group_name,
                        "Daily Velocity": f"${actual_velocity:,.0f}/day",
                        "Expected Velocity": f"${expected_velocity:,.0f}/day",
                        "Velocity Ratio": f"{velocity_ratio:.1f}%",
                        "Status": status
                    })
            
            if velocity_data:
                velocity_df = pd.DataFrame(velocity_data)
                st.dataframe(velocity_df, width="stretch")

        # 17. Seasonal Trend Analysis (Simulated)
        st.subheader("17. Seasonal Trend Analysis")
        seasonal_data = {
            "GroupA": {"Nov": 45000, "Dec": 48000, "Seasonal_Factor": 1.07},
            "GroupB": {"Nov": 38000, "Dec": 42000, "Seasonal_Factor": 1.11},
            "GroupC": {"Nov": 52000, "Dec": 58000, "Seasonal_Factor": 1.12},
            "Parts": {"Nov": 275000, "Dec": 305000, "Seasonal_Factor": 1.11}
        }
        
        seasonal_analysis = []
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0].lower()
                actual = group_data_single["Amount"].sum()
                
                # Simulate historical data
                historical_avg = seasonal_data.get(group_name.replace(" ", ""), {}).get("Dec", 50000)
                seasonal_factor = seasonal_data.get(group_name.replace(" ", ""), {}).get("Seasonal_Factor", 1.0)
                
                projected_monthly = (actual / 12) * 31  # Project full month
                vs_historical = ((projected_monthly / historical_avg - 1) * 100) if historical_avg > 0 else 0
                
                seasonal_analysis.append({
                    "Group": group_name,
                    "Projected Monthly": f"${projected_monthly:,.0f}",
                    "Historical Avg": f"${historical_avg:,.0f}",
                    "vs Historical": f"{vs_historical:+.1f}%",
                    "Seasonal Factor": f"{seasonal_factor:.2f}x"
                })
        
        if seasonal_analysis:
            seasonal_df = pd.DataFrame(seasonal_analysis)
            st.dataframe(seasonal_df, width="stretch")

        # 18. Budget Efficiency Scoring
        st.subheader("18. Budget Efficiency Scoring")
        efficiency_scores = []
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                budget = BUDGETS.get(group_key, 0)
                actual = group_data_single["Amount"].sum()
                
                # Efficiency metrics (0-100 scale)
                utilization_score = min(100, (actual / budget * 100)) if budget > 0 else 0
                consistency_score = max(0, 100 - (group_data_single["Amount"].std() / group_data_single["Amount"].mean() * 100)) if len(group_data_single) > 1 else 100
                timing_score = 85  # Simulated based on spending distribution
                
                composite_score = (utilization_score * 0.4 + consistency_score * 0.3 + timing_score * 0.3)
                
                grade = "A" if composite_score >= 90 else "B" if composite_score >= 80 else "C" if composite_score >= 70 else "D"
                
                efficiency_scores.append({
                    "Group": group_name,
                    "Utilization": f"{utilization_score:.1f}",
                    "Consistency": f"{consistency_score:.1f}",
                    "Timing": f"{timing_score:.1f}",
                    "Composite Score": f"{composite_score:.1f}",
                    "Grade": grade
                })
        
        if efficiency_scores:
            efficiency_df = pd.DataFrame(efficiency_scores)
            st.dataframe(efficiency_df, width="stretch")

        # 19. Variance Trend Prediction
        st.subheader("19. Variance Trend Prediction")
        prediction_data = []
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                budget = BUDGETS.get(group_key, 0)
                actual = group_data_single["Amount"].sum()
                
                # Simple trend prediction
                current_variance = actual - (budget * 12/31)
                daily_avg = actual / 12
                projected_month_end = daily_avg * 31
                predicted_variance = projected_month_end - budget
                
                trend = "📈 Increasing" if predicted_variance > current_variance else "📉 Decreasing"
                risk_level = "🔴 High" if abs(predicted_variance) > budget * 0.2 else "🟡 Medium" if abs(predicted_variance) > budget * 0.1 else "🟢 Low"
                
                prediction_data.append({
                    "Group": group_name,
                    "Current Variance": f"${current_variance:,.0f}",
                    "Predicted Variance": f"${predicted_variance:,.0f}",
                    "Trend": trend,
                    "Risk Level": risk_level
                })
        
        if prediction_data:
            prediction_df = pd.DataFrame(prediction_data)
            st.dataframe(prediction_df, width="stretch")

        # ===== MANAGEMENT CONTROLS SECTIONS =====
        
        # 20. Budget Reallocation Simulator
        st.subheader("20. Budget Reallocation Simulator")
        st.info("💡 Interactive Reallocation Tool")
        
        col1, col2 = st.columns(2)
        with col1:
            source_group = st.selectbox("Move Budget FROM:", options=list(groups))
        with col2:
            target_group = st.selectbox("Move Budget TO:", options=[g for g in groups if g != source_group])
        
        amount_to_move = st.slider("Amount to Reallocate ($)", 0, 10000, 1000, step=500)
        
        if st.button("Simulate Reallocation"):
            reallocation_results = []
            for group_name in groups:
                group_key = group_name.lower().replace(" ", "")
                original_budget = BUDGETS.get(group_key, 0)
                
                if group_name == source_group:
                    new_budget = original_budget - amount_to_move
                elif group_name == target_group:
                    new_budget = original_budget + amount_to_move
                else:
                    new_budget = original_budget
                
                actual = daily_usage[daily_usage["Group Name"] == group_name]["Amount"].sum() if not daily_usage.empty else 0
                new_utilization = (actual / new_budget * 100) if new_budget > 0 else 0
                
                reallocation_results.append({
                    "Group": group_name,
                    "Original Budget": f"${original_budget:,.0f}",
                    "New Budget": f"${new_budget:,.0f}",
                    "Change": f"${new_budget - original_budget:+,.0f}",
                    "New Utilization": f"{new_utilization:.1f}%"
                })
            
            reallocation_df = pd.DataFrame(reallocation_results)
            st.dataframe(reallocation_df, width="stretch")

        # 21. Approval Workflow Dashboard (Simulated)
        st.subheader("21. Approval Workflow Dashboard")
        
        # Simulate approval data
        import random
        approval_data = []
        for i in range(10):
            group = random.choice(list(groups))
            amount = random.randint(1000, 8000)
            status = random.choice(["⏳ Pending", "✅ Approved", "❌ Rejected", "🔄 Review"])
            days_pending = random.randint(1, 14)
            
            approval_data.append({
                "Request ID": f"REQ-{1000 + i}",
                "Group": group,
                "Amount": f"${amount:,}",
                "Status": status,
                "Days Pending": days_pending if "Pending" in status else "-",
                "Urgency": "🔴 High" if days_pending > 7 else "🟡 Medium" if days_pending > 3 else "🟢 Low"
            })
        
        approval_df = pd.DataFrame(approval_data)
        st.dataframe(approval_df, width="stretch")

        # 22. Budget Amendment History (Simulated)
        st.subheader("22. Budget Amendment History")
        amendment_history = [
            {"Date": "2025-11-15", "Group": "Parts", "Change": "+$15,000", "Reason": "Equipment upgrade", "Approved By": "CFO"},
            {"Date": "2025-11-08", "Group": "GroupC", "Change": "-$5,000", "Reason": "Project delay", "Approved By": "Director"},
            {"Date": "2025-10-22", "Group": "GroupA", "Change": "+$8,000", "Reason": "Additional resources", "Approved By": "Manager"},
        ]
        
        amendment_df = pd.DataFrame(amendment_history)
        st.dataframe(amendment_df, width="stretch")

        # 23. Spending Velocity Alerts
        st.subheader("23. Spending Velocity Alerts")
        velocity_alerts = []
        
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                budget = BUDGETS.get(group_key, 0)
                actual = group_data_single["Amount"].sum()
                
                daily_avg = actual / 12
                monthly_projection = daily_avg * 31
                velocity_vs_budget = (monthly_projection / budget * 100) if budget > 0 else 0
                
                if velocity_vs_budget > 120:
                    alert_type = "🚨 Overspending"
                elif velocity_vs_budget < 60:
                    alert_type = "⚠️ Underspending"
                else:
                    continue
                
                velocity_alerts.append({
                    "Group": group_name,
                    "Alert Type": alert_type,
                    "Projected Monthly": f"${monthly_projection:,.0f}",
                    "vs Budget": f"{velocity_vs_budget:.1f}%",
                    "Action Needed": "Review spending plan" if "Over" in alert_type else "Accelerate spending"
                })
        
        if velocity_alerts:
            velocity_alert_df = pd.DataFrame(velocity_alerts)
            st.dataframe(velocity_alert_df, width="stretch")
        else:
            st.success("✅ All groups have healthy spending velocity!")

        # ===== EXECUTIVE REPORTING SECTIONS =====
        
        # 24. Executive Summary Cards
        st.subheader("24. Executive Summary Cards")
        
        # Calculate key metrics
        total_budget = sum(BUDGETS.values())
        total_actual = filtered["Amount"].sum() if not filtered.empty else 0
        overall_utilization = (total_actual / total_budget * 100) if total_budget > 0 else 0
        
        # Executive metrics in columns
        exec_col1, exec_col2, exec_col3, exec_col4 = st.columns(4)
        
        with exec_col1:
            st.metric(
                "Overall Budget Utilization", 
                f"{overall_utilization:.1f}%",
                delta=f"{overall_utilization - 100:.1f}% vs target"
            )
        
        with exec_col2:
            groups_over_budget = sum(1 for row in comparison_data if float(row["Variance"].replace("$", "").replace(",", "")) > 0)
            st.metric(
                "Groups Over Budget", 
                f"{groups_over_budget}/{len(groups)}",
                delta="Requires attention" if groups_over_budget > 0 else "All on track"
            )
        
        with exec_col3:
            high_value_parts_count = len(filtered[filtered["Amount"] >= filtered["Amount"].quantile(0.9)]) if not filtered.empty else 0
            st.metric(
                "High Value Transactions", 
                high_value_parts_count,
                delta="Top 10% by value"
            )
        
        with exec_col4:
            projected_year_end = total_actual * 12  # Simple projection
            st.metric(
                "Projected Year-End", 
                f"${projected_year_end:,.0f}",
                delta=f"${projected_year_end - (total_budget * 12):+,.0f} vs annual"
            )

        # 25. Budget Performance Matrix
        st.subheader("25. Budget Performance Matrix")
        
        matrix_data = []
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                group_key = group_data_single["Group Key"].iloc[0]
                budget = BUDGETS.get(group_key, 0)
                actual = group_data_single["Amount"].sum()
                
                utilization = (actual / budget * 100) if budget > 0 else 0
                efficiency = 90 - abs(utilization - 85)  # Simulated efficiency score
                
                # Quadrant classification
                if utilization >= 90 and efficiency >= 85:
                    quadrant = "🟢 High Perform"
                elif utilization >= 90:
                    quadrant = "🟡 High Use/Low Eff"
                elif efficiency >= 85:
                    quadrant = "🔵 Low Use/High Eff"
                else:
                    quadrant = "🔴 Needs Attention"
                
                matrix_data.append({
                    "Group": group_name,
                    "Utilization %": f"{utilization:.1f}",
                    "Efficiency Score": f"{efficiency:.1f}",
                    "Performance Quadrant": quadrant
                })
        
        if matrix_data:
            matrix_df = pd.DataFrame(matrix_data)
            st.dataframe(matrix_df, width="stretch")

        # 26. ROI Impact Analysis (Simulated)
        st.subheader("26. ROI Impact Analysis")
        
        roi_data = [
            {"Group": "GroupA", "Investment": "$45,000", "Revenue Impact": "$180,000", "ROI": "300%", "Payback": "3 months"},
            {"Group": "GroupB", "Investment": "$38,000", "Revenue Impact": "$152,000", "ROI": "280%", "Payback": "3.2 months"},
            {"Group": "GroupC", "Investment": "$52,000", "Revenue Impact": "$156,000", "ROI": "200%", "Payback": "4 months"},
            {"Group": "Parts", "Investment": "$285,000", "Revenue Impact": "$855,000", "ROI": "200%", "Payback": "4 months"},
        ]
        
        roi_df = pd.DataFrame(roi_data)
        st.dataframe(roi_df, width="stretch")

        # 27. Comparative Benchmark
        st.subheader("27. Comparative Benchmark")
        
        benchmark_data = []
        for group_name in groups:
            group_data_single = daily_usage[daily_usage["Group Name"] == group_name]
            if not group_data_single.empty:
                actual = group_data_single["Amount"].sum()
                
                # Simulated industry benchmarks
                industry_avg = actual * random.uniform(0.8, 1.3)
                peer_avg = actual * random.uniform(0.9, 1.2)
                
                vs_industry = ((actual / industry_avg - 1) * 100) if industry_avg > 0 else 0
                vs_peer = ((actual / peer_avg - 1) * 100) if peer_avg > 0 else 0
                
                benchmark_data.append({
                    "Group": group_name,
                    "Our Spending": f"${actual:,.0f}",
                    "Industry Avg": f"${industry_avg:,.0f}",
                    "Peer Avg": f"${peer_avg:,.0f}",
                    "vs Industry": f"{vs_industry:+.1f}%",
                    "vs Peers": f"{vs_peer:+.1f}%"
                })
        
        if benchmark_data:
            benchmark_df = pd.DataFrame(benchmark_data)
            st.dataframe(benchmark_df, width="stretch")

        # ===== OPERATIONAL INSIGHTS SECTIONS =====
        
        # 28. Spending Pattern Anomalies
        st.subheader("28. Spending Pattern Anomalies")
        
        anomaly_threshold = st.slider("Anomaly Detection Sensitivity", 1.0, 3.0, 2.0, 0.1)
        
        anomalies = []
        if not filtered.empty:
            mean_amount = filtered["Amount"].mean()
            std_amount = filtered["Amount"].std()
            
            anomaly_transactions = filtered[
                (filtered["Amount"] > mean_amount + anomaly_threshold * std_amount) |
                (filtered["Amount"] < mean_amount - anomaly_threshold * std_amount)
            ]
            
            for _, row in anomaly_transactions.iterrows():
                anomaly_type = "📈 Unusually High" if row["Amount"] > mean_amount else "📉 Unusually Low"
                
                anomalies.append({
                    "Date": row["Date"],
                    "Part Name": row["Part Name"],
                    "Group": row["Group Name"],
                    "Amount": f"${row['Amount']:,.0f}",
                    "Anomaly Type": anomaly_type,
                    "Deviation": f"{abs(row['Amount'] - mean_amount) / std_amount:.1f}σ"
                })
        
        if anomalies:
            anomaly_df = pd.DataFrame(anomalies)
            st.dataframe(anomaly_df, width="stretch")
        else:
            st.success("✅ No spending anomalies detected!")

        # 29. Vendor/Supplier Analysis (Simulated)
        st.subheader("29. Vendor/Supplier Analysis")
        
        vendors = ["Supplier A", "Supplier B", "Supplier C", "Supplier D", "Supplier E"]
        vendor_data = []
        
        for vendor in vendors:
            spend = random.randint(25000, 150000)
            transactions = random.randint(5, 25)
            avg_order = spend / transactions
            rating = random.uniform(3.5, 5.0)
            
            vendor_data.append({
                "Vendor": vendor,
                "Total Spend": f"${spend:,.0f}",
                "Transactions": transactions,
                "Avg Order Value": f"${avg_order:,.0f}",
                "Performance Rating": f"{rating:.1f}/5.0",
                "Status": "🟢 Preferred" if rating >= 4.5 else "🟡 Standard" if rating >= 4.0 else "🔴 Review"
            })
        
        vendor_df = pd.DataFrame(vendor_data)
        st.dataframe(vendor_df, width="stretch")

        # 30. Seasonal Budget Calendar
        st.subheader("30. Seasonal Budget Calendar")
        
        # Create a simple calendar view
        calendar_data = {
            "Week 1": {"Planned": 25, "Actual": 30, "Status": "🟡"},
            "Week 2": {"Planned": 25, "Actual": 28, "Status": "🟡"},
            "Week 3": {"Planned": 25, "Actual": 22, "Status": "🟢"},
            "Week 4": {"Planned": 25, "Actual": 20, "Status": "🟢"}
        }
        
        cal_df = pd.DataFrame(calendar_data).T.reset_index()
        cal_df.columns = ["Period", "Planned %", "Actual %", "Status"]
        st.dataframe(cal_df, width="stretch")

        # 31. Resource Constraint Tracker
        st.subheader("31. Resource Constraint Tracker")
        
        constraints = [
            {"Resource": "Budget Capacity", "Utilization": "78%", "Constraint Level": "🟢 Low", "Impact": "Minimal"},
            {"Resource": "Approval Bandwidth", "Utilization": "92%", "Constraint Level": "🟡 Medium", "Impact": "Delays possible"},
            {"Resource": "Vendor Capacity", "Utilization": "85%", "Constraint Level": "🟡 Medium", "Impact": "Lead time increase"},
            {"Resource": "Internal Resources", "Utilization": "95%", "Constraint Level": "🔴 High", "Impact": "Process bottleneck"}
        ]
        
        constraint_df = pd.DataFrame(constraints)
        st.dataframe(constraint_df, width="stretch")

        # ===== INTERACTIVE FEATURES SECTIONS =====
        
        # 32. Mobile-Friendly Summary
        st.subheader("32. Mobile-Friendly Summary")
        
        mobile_summary = {
            "🎯 Budget Status": f"{overall_utilization:.0f}% utilized",
            "⚠️ Alerts": f"{groups_over_budget} groups over budget",
            "💰 Top Spend": f"${filtered['Amount'].max():,.0f}" if not filtered.empty else "$0",
            "📈 Trend": "↗️ Increasing" if overall_utilization > 85 else "➡️ Stable",
            "🎛️ Control": "✅ On Track" if groups_over_budget == 0 else "❌ Needs Action"
        }
        
        for key, value in mobile_summary.items():
            st.metric(key, value)

        # 33. Export Options
        st.subheader("33. Export to Excel")
        
        if st.button("📊 Generate Excel Report"):
            st.success("✅ Excel report generated! (Feature simulated)")
            st.info("Report would include: Budget vs Actual, Transactions, Forecasts, Alerts")

        # 34. Real-time Notifications (Simulated)
        st.subheader("34. Real-time Notifications")
        
        notification_settings = {
            "Budget Threshold Alerts": st.checkbox("Enable budget threshold notifications", True),
            "High-Value Purchase Alerts": st.checkbox("Enable high-value purchase alerts", True),
            "Velocity Warnings": st.checkbox("Enable spending velocity warnings", False),
            "Weekly Summaries": st.checkbox("Enable weekly summary emails", True)
        }
        
        if st.button("💾 Save Notification Preferences"):
            st.success("✅ Notification preferences saved!")

        # 35. Custom Filter Builder
        st.subheader("35. Custom Filter Builder")
        
        st.info("🔧 Build Your Custom Analysis")
        
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            custom_group = st.multiselect("Select Groups:", options=list(groups), default=list(groups))
        with filter_col2:
            amount_range = st.slider("Amount Range ($)", 0, int(filtered["Amount"].max()) if not filtered.empty else 10000, (0, 5000))
        
        date_range = st.date_input("Date Range:", value=[pd.to_datetime("2025-12-01").date(), pd.to_datetime("2025-12-12").date()])
        
        if st.button("🔍 Apply Custom Filter"):
            # Apply custom filters (simulation)
            custom_filtered = filtered[
                (filtered["Group Name"].isin(custom_group)) &
                (filtered["Amount"] >= amount_range[0]) &
                (filtered["Amount"] <= amount_range[1])
            ]
            
            if not custom_filtered.empty:
                st.write(f"📊 Custom Analysis Results: {len(custom_filtered)} transactions found")
                st.dataframe(custom_filtered, width="stretch")
            else:
                st.warning("No transactions match your custom criteria.")


if __name__ == "__main__":
    main()
