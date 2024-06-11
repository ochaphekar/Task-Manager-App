"""
This file defines actions, i.e. functions the URLs are mapped into
The @action(path) decorator exposed the function at URL:

    http://127.0.0.1:8000/{app_name}/{path}

If app_name == '_default' then simply

    http://127.0.0.1:8000/{path}

If path == 'index' it can be omitted:

    http://127.0.0.1:8000/

The path follows the bottlepy syntax.

@action.uses('generic.html')  indicates that the action uses the generic.html template
@action.uses(session)         indicates that the action uses the session
@action.uses(db)              indicates that the action uses the db
@action.uses(T)               indicates that the action uses the i18n & pluralization
@action.uses(auth.user)       indicates that the action requires a logged in user
@action.uses(auth)            indicates that the action requires the auth object

session, db, T, auth, and tempates are examples of Fixtures.
Warning: Fixtures MUST be declared with @action.uses({fixtures}) else your app will result in undefined behavior
"""

from py4web import action, request, abort, redirect, URL
from py4web.utils.form import Form, FormStyleBulma
from yatl.helpers import A
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash
from datetime import datetime, timedelta

@action("index")
@action.uses("index.html", auth.user, T)
def index():
    user = auth.get_user()
    
    if user:
        user_record = db(db.user.email == user['email']).select().first()
        
        if not user_record:
            # Insert the user into the user table if they do not exist
            db.user.insert(username=user['username'], name=f"{user['first_name']} {user['last_name']}", email=user['email'])
            db.commit()
            user_record = db(db.user.email == user['email']).select().first()
        
        message = T("Hello {name}").format(name=user_record.name)
    else:
        redirect(URL('auth/login'))
        message = T("Hello")
    
    return dict(message=message)

@action('current_user', method=['GET'])
@action.uses(db, auth.user)
def current_user():
    auth_user = auth.get_user().get('id')
    current_user = db(db.user.id == auth_user).select().first()
    #print(current_user)
    #print(current_user.manager)
    manager_name = None


    if current_user.manager:
        manager = db(db.user.id == current_user.manager).select().first()
        #print(manager)
        if manager:
            manager_name = manager.name
            
        
    if not auth_user:
        return dict(error="No user logged in")
    print(manager_name)
    return dict(user=dict(id=auth_user, name=current_user.name, email=current_user.email, manager_name=manager_name))

@action('get_users', method=['GET'])
@action.uses(db)
def get_users():
    users = db(db.auth_user).select().as_list()
    #print(users)
    return dict(users=users)

@action('select_manager', method=['POST'])
@action.uses(db, auth.user)
def select_manager():
    user = auth.get_user()
    user_id = user.get('id')
    
    manager_id = request.json.get('manager_id')

    #print(f"user_id: {user_id}")
    #print(f"manager_id: {manager_id}")
    

    # Update the user's manager 
    db(db.user.id == user_id).update(manager=manager_id)
    db.commit()
    
    # Fetch the manager record from the auth_user table
    manager_record = db(db.auth_user.id == manager_id).select().first() if manager_id else None

    #print(manager_record)
    if manager_record:
        manager_name = manager_record.get('first_name')
        print(manager_name)
    else:
        manager_name = None
        print(f"No manager found for manager_id: {manager_id}")
    
    # Update or insert manager assignment
    #db.manager_assignment.update_or_insert(
        #(db.manager_assignment.created_by == user_id),
        #manager=manager_id
    #)
    all_users = db(db.user).select()
    print(f"All users: {all_users.as_list()}")
    
    return dict(message="Manager updated")


@action('edit_task/<task_id:int>', method=['PUT'])
@action.uses(db, auth.user)
def edit_task(task_id):
    print(task_id)
    task = db(db.tasks_table.id == task_id).select().first()
    print(task)
    if not task:
        return dict(error="Task not found")

    # Check if the user is the creator or a manager of the creator
    is_creator = task.created_by == auth.get_user().get('id')
    is_manager = (db(db.user.id == task.created_by).select().first().manager == auth.get_user().get('id'))
    print(is_creator)
    print(is_manager)
    
    if not is_creator and not is_manager:
        return dict(error="Not Authorized")
    print(task.assigned_to)



    updated = db(db.tasks_table.id == task_id).update(
        title=request.json.get('title', task.title),
        description=request.json.get('description', task.description),
        status=request.json.get('status', task.status),
        assigned_to=request.json.get('assigned_to', task.assigned_to),
        deadline=request.json.get('deadline', task.deadline)
    )
    db.commit()
    if(updated):
        return dict(message="Task updated")
    else:
        return dict(error="Failed to update task")


@action('filter_tasks', method=['POST'])
@action.uses(db, auth.user)
def filter_tasks():
    criteria = request.json
    print(criteria)
    #print(criteria.get('created_by_user'))
    query = (db.tasks_table.id > 0)
    
    if 'date_created' in criteria:
        date_created = datetime.strptime(criteria.get('date_created'), '%Y-%m-%d')
        next_day = date_created + timedelta(days=1)
        query &= (db.tasks_table.created_on >= date_created) & (db.tasks_table.created_on < next_day)
    if 'deadline' in criteria:
        deadline_date = datetime.strptime(criteria.get('deadline'), '%Y-%m-%d')
        next_day = deadline_date + timedelta(days=1)
        query &= (db.tasks_table.deadline >= deadline_date) & (db.tasks_table.deadline < next_day)
    if 'status' in criteria:
        query &= (db.tasks_table.status == criteria.get('status'))
    if 'created_by' in criteria:
        query &= (db.tasks_table.created_by == criteria.get('created_by'))
    if 'assigned_to' in criteria:
        query &= (db.tasks_table.assigned_to == criteria.get('assigned_to'))
    
    if criteria.get('criteria') == 'created-by-self':
        #print('success')
        query &= (db.tasks_table.created_by == auth.get_user().get('id'))
    if criteria.get('criteria') == 'assigned-to-self':
        query &= (db.tasks_table.assigned_to == auth.get_user().get('id'))
    if criteria.get('criteria') == 'managed-by-self-assign':
        current_user_id = auth.get_user().get('id')
        managed_users = db(db.user.manager == current_user_id).select(db.user.id)
        managed_user_ids = [user.id for user in managed_users]
        query &= (db.tasks_table.assigned_to.belongs(managed_user_ids))
    if criteria.get('criteria') == 'managed-by-self':
        print('manager')
        current_user_id = auth.get_user().get('id')
        print(current_user_id)
        managed_users = db(db.user.manager == current_user_id).select(db.user.id)
        print(managed_users)
        managed_user_ids = [user.id for user in managed_users]
        query &= (db.tasks_table.created_by.belongs(managed_user_ids))
    
    tasks = db(query).select().as_list()
    return dict(tasks=tasks)

@action('create_task', method=['GET', 'POST'])
@action.uses(db, auth.user) 
def create_task():
    if request.method == 'GET':
        tasks_list = db(db.tasks_table).select()
        print(tasks_list)
        return dict(tasks = tasks_list)
    elif request.method == 'POST':
        task_id = db.tasks_table.insert(
            title=request.json.get('title'),
            description=request.json.get('description'),
            status = request.json.get('status'),
            assigned_to=request.json.get('assigned_to'),
            deadline=request.json.get('deadline'),
        )
        db.commit()

        return dict(task_id=task_id)

@action('add_comment/<task_id:int>', method=['POST'])
@action.uses(db, auth.user)
def add_comment(task_id):
    comment_text = request.json.get('comment')
    if not comment_text:
        return dict(error="Comment text is required")

    db.comments.insert(
        task_id=task_id,
        comment=comment_text,
        #created_by=auth.get_user().get('id')
    )
    return dict(message="Comment added successfully")
@action('get_comments/<task_id:int>', method=['GET'])
@action.uses(db, auth.user)
def get_comments(task_id):
    comments = db(db.comments.task_id == task_id).select(orderby=db.comments.created_on).as_list()
    print(comments)
    return dict(comments=comments)

@action('view_task/<task_id:int>')
@action.uses('view_task.html', db, auth.user)
def view_task(task_id):
    task = db.task[task_id]
    if not task:
        abort(404, "Task not found")
    comments = db(db.comment.task_id == task_id).select()
    return dict(task=task, comments=comments)


@action('delete_task/<task_id:int>', method=['DELETE'])
@action.uses(db, auth.user)
def delete_task(task_id):
    # Retrieve the task
    task = db(db.tasks_table.id == task_id).select().first()
    if not task:
        return dict(error="Task not found")

    # Check if the user is the creator or a manager of the creator
    is_creator = task.created_by == auth.get_user().get('id')
    is_manager = (db(db.user.id == task.created_by).select().first().manager == auth.get_user().get('id'))

    if not is_creator and not is_manager:
        return dict(error="Not Authorized")

    # Delete the task
    db(db.tasks_table.id == task_id).delete()

    return dict(message="Task deleted successfully")
