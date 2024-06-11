"""
This file defines the database models
"""

from .common import *
from pydal.validators import *
from py4web import DAL, Field
from datetime import datetime

# Define the Users table
db.define_table('user',
                Field('username'),
                Field('name'),
                Field('email'),
                Field('manager', 'reference user'),
                auth.signature
                )  # Self-reference for manager

# Define the Tasks table
db.define_table('tasks_table',
                Field('title'),
                Field('id', "integer", requires=IS_NOT_EMPTY(), default=0),
                Field('description', 'text'),
                #Field('created_by', 'reference user'),
                Field('deadline', 'datetime'),
                Field('status', requires=IS_IN_SET(['pending', 'acknowledged', 'rejected', 'completed', 'failed'])),
                Field('assigned_to', 'reference user', requires=IS_EMPTY_OR(IS_IN_DB(db, 'user.id', '%(name)s'))),
                auth.signature
                )

# Define the Comments table
db.define_table('comments',
                Field('task_id', 'reference tasks_table'),
                Field('comment', 'text'),
                #Field('created_by', 'reference user'),
                auth.signature)

db.define_table('manager_assignment',
    Field("manager", "reference auth_user"),
    auth.signature
)

db.commit()
