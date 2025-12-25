from datetime import datetime, timezone
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import sqlalchemy as sa
import sqlalchemy.orm as so
from hashlib import md5
from app import db, login


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

followers = sa.Table(
    'followers',
    db.metadata,
    sa.Column('follower_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True),
    sa.Column('followed_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True)
)

bookmarks = sa.Table(
    'bookmarks',
    db.metadata,
    sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True),
    sa.Column('post_id', sa.Integer, sa.ForeignKey('post.id'), primary_key=True),
    sa.Column('timestamp', sa.DateTime, default=lambda: datetime.now(timezone.utc))
)

class User(UserMixin,db.Model): 
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))

    posts: so.WriteOnlyMapped['Post'] = so.relationship(back_populates='author')
    
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda:datetime.now(timezone.utc))
    konum: so.Mapped[Optional[str]] = so.mapped_column(sa.String(100))
    
    bookmarked_posts: so.WriteOnlyMapped['Post'] = so.relationship(
        secondary=bookmarks,
        back_populates='bookmarked_by',
        passive_deletes=True
    )

    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'
    
    following: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        back_populates='followers')
    
    followers: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates='following')
    

    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)
    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)
    def is_following(self, user):
        query = self.following.select().where(User.id == user.id)
        return db.session.execute(query).first() is not None
    def followers_count(self):
        query = sa.select(sa.func.count()).select_from(self.followers.select().subquery())
        return db.session.scalar(query)
    def following_count(self):
        query = sa.select(sa.func.count()).select_from(self.following.select().subquery())
        return db.session.scalar(query)
    def following_posts(self):
        Author = so.aliased(User)
        Follower = so.aliased(User)
        return(
            sa.select(Post)
            .join(Post.author.of_type(Author))
            .join(Author.followers.of_type(Follower), isouter=True)
            .where(sa.or_(Follower.id == self.id, Author.id == self.id,))
            .group_by(Post)
            .order_by(Post.timestamp.desc())
        )
    def owner_posts(self):
        return(
            sa.select(Post)
            .where(Post.user_id == self.id)
            .order_by(Post.timestamp.desc())
        )


    def bookmark(self, post):
        if not self.has_bookmarked(post):
            stmt = bookmarks.insert().values(
                user_id=self.id, 
                post_id=post.id, 
                timestamp=datetime.now(timezone.utc)
            )
            db.session.execute(stmt)

    def unbookmark(self, post):
        if self.has_bookmarked(post):
            stmt = bookmarks.delete().where(
                bookmarks.c.user_id == self.id,
                bookmarks.c.post_id == post.id
            )
            db.session.execute(stmt)

    def has_bookmarked(self, post):
        query = self.bookmarked_posts.select().where(Post.id == post.id)
        return db.session.scalar(query) is not None
    
    def bookmarked_posts_list(self, sort_by='bookmark_newest'):
        query = sa.select(Post).join(bookmarks, (bookmarks.c.post_id == Post.id)).where(bookmarks.c.user_id == self.id)
        
        if sort_by == 'bookmark_newest':
            query = query.order_by(bookmarks.c.timestamp.desc()) 
        elif sort_by == 'bookmark_oldest':
            query = query.order_by(bookmarks.c.timestamp.asc())  
        elif sort_by == 'post_newest':
            query = query.order_by(Post.timestamp.desc())        
        elif sort_by == 'post_oldest':
            query = query.order_by(Post.timestamp.asc())         
        else:
            query = query.order_by(bookmarks.c.timestamp.desc()) 
            
        return query
    
class Post(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(index = True, default=lambda:datetime.now(timezone.utc))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index = True)
    author: so.Mapped[User] = so.relationship(back_populates='posts')


    comments: so.WriteOnlyMapped['Comment'] = so.relationship(back_populates='comment_author')

    def __repr__(self):
        return '<Post {}>'.format(self.body)
    
    bookmarked_by: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=bookmarks,
        back_populates='bookmarked_posts'
    )
    

class Comment(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    content: so.Mapped[str] = so.mapped_column(sa.String(300))
    timestamp: so.Mapped[datetime] = so.mapped_column(index = True, default=lambda:datetime.now(timezone.utc))
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id), index = True)
    comment_author: so.Mapped[Post] = so.relationship(back_populates='comments')

    def __repr__(self):
        return '<Post {}>'.format(self.content)
    


