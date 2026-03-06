def make_chart(d, ticker, stop_price, target_2r, target_3r):
    df = d["df"].tail(180).copy()

    # ── Panel heights: price bigger, volume/RS smaller ────────
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.65, 0.18, 0.17],
        subplot_titles=(None, None, None)
    )

    # ── 1. Candlesticks — thinner wicks, crisper bodies ───────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        increasing=dict(
            line=dict(color="#00c076", width=1),
            fillcolor="#00c076"
        ),
        decreasing=dict(
            line=dict(color="#ff4d4d", width=1),
            fillcolor="#ff4d4d"
        ),
        whiskerwidth=0.3,
        name="Price",
        showlegend=False
    ), row=1, col=1)

    # ── 2. Moving Averages — crisp, styled like barchart ──────
    ma_styles = [
        ("SMA50",  "#f5c518", 1.5, "SMA 50"),
        ("SMA150", "#ff8c00", 1.5, "SMA 150"),
        ("SMA200", "#e040fb", 2.0, "SMA 200"),
    ]
    for col, color, width, label in ma_styles:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col],
            name=label,
            line=dict(color=color, width=width, shape="spline", smoothing=0.3),
            hovertemplate=f"{label}: %{{y:.2f}}<extra></extra>"
        ), row=1, col=1)

    # ── 3. Price level lines — annotations right-side aligned ─
    price_levels = [
        (d["pivot"],   "#00e5ff", "dash",     f"Pivot  ${d['pivot']:.2f}"),
        (stop_price,   "#ff4d4d", "dot",      f"Stop   ${stop_price:.2f}"),
        (target_2r,    "#00c076", "dashdot",  f"2R     ${target_2r:.2f}"),
        (target_3r,    "#69f0ae", "dashdot",  f"3R     ${target_3r:.2f}"),
    ]
    for level, color, dash, label in price_levels:
        fig.add_hline(
            y=level, row=1, col=1,
            line=dict(color=color, width=1.2, dash=dash),
            annotation=dict(
                text=label,
                font=dict(size=10, color=color, family="monospace"),
                bgcolor="rgba(13,17,23,0.75)",
                bordercolor=color,
                borderwidth=1,
                borderpad=3,
                xref="paper", x=1.0,
                xanchor="left"
            )
        )

    # ── 4. Current price line ─────────────────────────────────
    fig.add_hline(
        y=d["price"], row=1, col=1,
        line=dict(color="rgba(255,255,255,0.35)", width=1, dash="dot"),
        annotation=dict(
            text=f"  ${d['price']:.2f}",
            font=dict(size=10, color="white", family="monospace"),
            bgcolor="rgba(13,17,23,0.6)",
            xref="paper", x=0,
            xanchor="right"
        )
    )

    # ── 5. Volume bars — green/red with 50MA line ─────────────
    vol_colors = []
    for i in range(len(df)):
        if df["Close"].iloc[i] >= df["Open"].iloc[i]:
            vol_colors.append("rgba(0,192,118,0.65)")
        else:
            vol_colors.append("rgba(255,77,77,0.65)")

    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        marker=dict(color=vol_colors, line=dict(width=0)),
        name="Volume",
        showlegend=False,
        hovertemplate="Vol: %{y:,.0f}<extra></extra>"
    ), row=2, col=1)

    # Volume MA line
    fig.add_trace(go.Scatter(
        x=df.index, y=df["VolAvg50"],
        name="Vol MA50",
        line=dict(color="#f5c518", width=1.2, dash="solid"),
        showlegend=False,
        hovertemplate="VolMA50: %{y:,.0f}<extra></extra>"
    ), row=2, col=1)

    # ── 6. RS Line vs SMA200 ──────────────────────────────────
    rs_line = df["Close"] / df["SMA200"]
    rs_new_high = float(rs_line.iloc[-1]) >= float(rs_line.tail(60).max()) * 0.99
    rs_color    = "#00c076" if rs_new_high else "#ab47bc"

    fig.add_trace(go.Scatter(
        x=df.index, y=rs_line,
        name="RS Line",
        line=dict(color=rs_color, width=1.5, shape="spline", smoothing=0.3),
        fill="tozeroy",
        fillcolor=f"rgba({','.join(str(int(rs_color.lstrip('#')[i:i+2], 16)) for i in (0,2,4))},0.08)",
        showlegend=False,
        hovertemplate="RS: %{y:.3f}<extra></extra>"
    ), row=3, col=1)

    # RS new high marker
    if rs_new_high:
        fig.add_annotation(
            x=df.index[-1], y=float(rs_line.iloc[-1]),
            text="★ RS NEW HIGH",
            font=dict(size=9, color="#00c076", family="monospace"),
            bgcolor="rgba(0,192,118,0.15)",
            bordercolor="#00c076",
            borderwidth=1,
            showarrow=False,
            row=3, col=1,
            xanchor="right"
        )

    # ── 7. Layout — barchart-style dark pro theme ─────────────
    fig.update_layout(
        height=780,
        paper_bgcolor="#0a0e17",
        plot_bgcolor="#0a0e17",
        font=dict(family="monospace, Consolas", size=11, color="#c9d1d9"),
        margin=dict(t=55, b=10, l=65, r=120),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#161b22",
            bordercolor="#30363d",
            font=dict(family="monospace", size=11, color="#e6edf3")
        ),
        legend=dict(
            orientation="h",
            x=0, y=1.04,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color="#8b949e"),
            itemclick=False
        ),
        title=dict(
            text=(
                f"<b>{ticker}</b>  "
                f"<span style='color:#8b949e'>|</span>  "
                f"<b style='color:#00c076'>${d['price']:.2f}</b>  "
                f"<span style='color:#8b949e'>|  TT: </span>"
                f"<b style='color:#f5c518'>{d['tt_score']}/8</b>  "
                f"<span style='color:#8b949e'>|  {d['stage_label']}  |  VCP: </span>"
                f"<b style='color:#58a6ff'>{d['vcp_score']}/100</b>"
            ),
            font=dict(size=13, color="#e6edf3", family="monospace"),
            x=0.01, xanchor="left"
        )
    )

    # ── 8. Axes — subtle grid like barchart ───────────────────
    axis_style = dict(
        showgrid=True,
        gridcolor="rgba(48,54,61,0.6)",
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor="#30363d",
        linewidth=1,
        tickfont=dict(size=10, color="#8b949e", family="monospace"),
        tickformat="$,.0f",
    )

    fig.update_yaxes(**axis_style, row=1, col=1)
    fig.update_yaxes(
        **{**axis_style, "tickformat": ".2s"},
        title=dict(text="VOL", font=dict(size=9, color="#8b949e")),
        row=2, col=1
    )
    fig.update_yaxes(
        **{**axis_style, "tickformat": ".3f"},
        title=dict(text="RS", font=dict(size=9, color="#8b949e")),
        row=3, col=1
    )

    x_axis_style = dict(
        showgrid=False,
        showline=True,
        linecolor="#30363d",
        tickfont=dict(size=10, color="#8b949e", family="monospace"),
        rangeslider_visible=False,
    )
    fig.update_xaxes(**x_axis_style)

    # Hide x-axis labels on top two panels
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)

    # Crosshair cursor
    fig.update_layout(
        xaxis=dict(showspikes=True, spikecolor="#444c56", spikethickness=1, spikedash="dot"),
        xaxis2=dict(showspikes=True, spikecolor="#444c56", spikethickness=1, spikedash="dot"),
        xaxis3=dict(showspikes=True, spikecolor="#444c56", spikethickness=1, spikedash="dot"),
        yaxis=dict(showspikes=True, spikecolor="#444c56", spikethickness=1, spikedash="dot"),
    )

    return fig
