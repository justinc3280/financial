from app import db

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse

from app.auth import auth
from app.auth.forms import LoginForm, RegistrationForm
from app.models import User


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('finance.index'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('finance.index')

        return redirect(next_page)
    return render_template('auth/forms/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('User has been logged out')
    return redirect(url_for('finance.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('finance.index'))

    form = RegistrationForm()

    if form.validate_on_submit():
        existing_user_username = User.query.filter_by(
            username=form.username.data
        ).first()
        existing_user_email = User.query.filter_by(email=form.email.data).first()

        if existing_user_username:
            flash('Username is taken')
        if existing_user_email:
            flash('Email address is already in use')
        if existing_user_username or existing_user_email:
            return redirect(url_for(auth.register))

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('finance.index'))
    return render_template('auth/forms/register.html', form=form)
