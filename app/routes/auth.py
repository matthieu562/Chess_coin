from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app import db
from app.models import User


auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            session['username'] = user.username
            return redirect(url_for('home.homepage'))
        flash("Incorrect username or password", "danger")
    return render_template(
        template_name_or_list='login.html'
    )

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
            return redirect(url_for('auth.register'))
        password = request.form['password']
        user = User(username=username, available_funds=10000)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['username'] = user.username
        return redirect(url_for('home.homepage'))
    return render_template(
        template_name_or_list='register.html'
    )

@auth.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('auth.login'))
