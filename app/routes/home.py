from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.models import HoverTool, Legend
from bokeh.resources import CDN
from flask import Blueprint, redirect, render_template, session, url_for

from app.utils.chess_api import get_elo_df


home = Blueprint('home', __name__)


@home.route('/')
def homepage():
    return redirect(url_for('home.elo_page'))


@home.route('/elo')
def elo_page():
    df = get_elo_df()

    # Création du plot Bokeh
    p = figure(
        x_axis_type='datetime',
        sizing_mode="stretch_width",
        height=400,
        tools="pan,wheel_zoom,box_zoom,reset,save"
    )

    line = p.line(df['Date'], df['ELO'], line_width=2)
    p.scatter(df['Date'], df['ELO'], size=4, marker="circle", fill_color="black")

    legend = Legend(items=[("Loïc Coin", [line])])
    legend.label_text_font_size = "13px"
    p.add_layout(legend, 'below')  # En dehors à droite

    p.xaxis.axis_label = 'Date'
    p.yaxis.axis_label = 'ELO'

    hover = HoverTool(
        tooltips=[("Date", "@x{%F %T}"), ("ELO", "@y")],
        formatters={'@x': 'datetime'},
        mode='vline'
    )
    p.add_tools(hover)

    script, div = components(p)
    cdn_js = CDN.js_files[0]
    cdn_css = CDN.css_files[0] if CDN.css_files else None

    return render_template(
        template_name_or_list='home.html',
        username=session.get('username'),
        elo_rapid=df.iloc[-1]["ELO"],
        script=script,
        div=div,
        cdn_js=cdn_js,
        cdn_css=cdn_css
    )
