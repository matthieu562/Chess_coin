from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.models import HoverTool, Legend
from bokeh.resources import CDN
from flask import Blueprint, redirect, render_template, session, url_for, request, jsonify

from app.utils.chess_api import get_elo_df, get_current_elo
from config import CHESS_MAPPING, LOIC_USERNAME


home = Blueprint('home', __name__)


@home.route('/')
def homepage():
    return redirect(url_for('home.elo_page'))


@home.route('/elo')
def elo_page():
    df = get_elo_df(session.get('selected_chess_com_tag', LOIC_USERNAME))

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
        elo_rapid=session.get(
            'selected_chess_com_tag_value',
            get_current_elo(
                session.get('selected_chess_com_tag', LOIC_USERNAME)
            )
        ),
        script=script,
        div=div,
        cdn_js=cdn_js,
        cdn_css=cdn_css,
        assets=list(CHESS_MAPPING.keys())
    )

@home.route('/update_selected_asset_for_home', methods=['POST'])
def update_selected_asset():
    data = request.get_json()
    selected_asset = data.get('asset')

    if not selected_asset:
        return jsonify({'status': 'error', 'message': 'No asset provided'}), 400

    session['selected_asset'] = selected_asset
    session['selected_chess_com_tag'] = CHESS_MAPPING[selected_asset]
    new_elo = get_current_elo(session.get('selected_chess_com_tag'))
    session['selected_chess_com_tag_value'] = new_elo

    df = get_elo_df(session.get('selected_chess_com_tag', LOIC_USERNAME))

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

    return jsonify(
        {
            'status': 'ok', 'selected': selected_asset, 'elo_rapid': new_elo,
            'script': script, 'div': div
        }
    )
