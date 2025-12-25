from flask import render_template, flash, redirect, url_for, request
from app import app
from app.forms import LoginForm, ForgetPasswordForm, RegistrationForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app import db
from app.models import User, Post
from app.forms import EditProfileForm, EmptyForm, PostForm
from urllib.parse import urlsplit
from datetime import datetime, timezone

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Gönderi başarıyla eklendi!')
        return redirect(url_for('index'))

    posts = db.session.scalars(current_user.following_posts()).all()

    return render_template("index.html", title='Home', form=form, posts=posts)


@app.route('/about')
def about():
    return render_template('about.html')
# end def

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm() 
    
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Tebrikssssss!')
        return redirect(url_for('login'))
    
    return render_template('register.html', title='Register', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password' )
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@app.route('/forget', methods = ['GET', 'POST'])
def forget():
    form = ForgetPasswordForm()
    return render_template('forget.html', title='Forget Password', form=form)

@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))

    followers_list = db.session.scalars(user.followers.select()).all()
    following_list = db.session.scalars(user.following.select()).all()

    posts = db.session.scalars(user.owner_posts()).all()

    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts, form=form, followers_list=followers_list, following_list=following_list)


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(original_username=current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        current_user.konum = form.konum.data
        db.session.commit()
        flash('Değişiklikler kaydedildi.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.konum.data = current_user.konum
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@app.route('/user/<username>/followers', methods=['GET'])
@login_required
def followers(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))

    followers_list = db.session.scalars(user.followers.select()).all()

    return render_template('followers.html', user=user, followers_list=followers_list)

@app.route('/user/<username>/following', methods=['GET'])
@login_required
def following(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    following_list = db.session.scalars(user.following.select()).all()

    return render_template('following.html', user=user, following_list=following_list)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/patlat')
def patlat():
    return 1 / 0

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f'Kullanıcı {username} bulunamadı.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('Kendini takip edemezsin!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'{username} isimli kullanıcı takip edildi!')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))
    
@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f'Kullanıcı {username} bulunamadı.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('Kendini takip edemezsiniz!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'{username} isimli kullanıcı takipten çıkartıldı!')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))
    
@app.route('/explore')
@login_required
def explore():
    query=sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.session.scalars(query).all()
    form = EmptyForm()
    return render_template('explore.html', title='Explore', posts=posts, form=form)

@app.route('/bookmark/<int:post_id>', methods=['POST'])
@login_required
def bookmark_post(post_id):
    form = EmptyForm()
    if form.validate_on_submit():
        post = db.session.scalar(sa.select(Post).where(Post.id == post_id))
        if post is None:
            flash('Post bulunamadı.')
            return redirect(url_for('index'))
        if current_user.has_bookmarked(post):
            flash('Bu gönderi zaten kaydedilmiş.')
        else:
            current_user.bookmark(post)
            db.session.commit()
            flash('Gönderi kaydedildi!')
    return redirect(request.referrer or url_for('index'))

@app.route('/unbookmark/<int:post_id>', methods=['POST'])
@login_required
def unbookmark_post(post_id):
    form = EmptyForm()
    if form.validate_on_submit():
        post = db.session.scalar(sa.select(Post).where(Post.id == post_id))
        if post is None:
            flash('Post bulunamadı.')
            return redirect(url_for('index'))
        if current_user.has_bookmarked(post):
            current_user.unbookmark(post)
            db.session.commit()
            flash('Gönderi kaydedilenlerden çıkarıldı.')
    return redirect(request.referrer or url_for('index'))

@app.route('/bookmarks')
@login_required
def bookmarks():
    sort_by = request.args.get('sort_by', 'bookmark_newest')
    
    query = current_user.bookmarked_posts_list(sort_by=sort_by)
    posts = db.session.scalars(query).all()
    
    form = EmptyForm()
    return render_template('bookmarks.html', title='Kaydedilenler', posts=posts, form=form, current_sort=sort_by)