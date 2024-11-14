import json
from fastapi import FastAPI, Depends, HTTPException, Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2AuthorizationCodeBearer
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from databases import Database
from jose import JWTError, jwt
import requests
import datetime
import syslog

app = FastAPI()
templates = Jinja2Templates(directory="../html")

# -------------------------------Database--------------------------------
Base = declarative_base()
DATABASE_URL = "sqlite:///./database.db"
# DATABASE_URL = "mysql+pymysql://admin:Motdepasse1!@todolist-database.c5uwuy0ymmo8.us-east-1.rds.amazonaws.com:3306/todolist_database"

class TaskModel(Base):
    __tablename__ = "Task"
    id = Column(Integer, primary_key=True, index=True)
    userId = Column(String(255))
    taskName = Column(String(255))
    taskDescription = Column(String(255), nullable=True)
    taskPriority = Column(Integer, nullable=True)
    taskStatus = Column(Integer, nullable=True)
    taskDeadline = Column(DateTime, nullable=True)

try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    database = Database(DATABASE_URL)

    Base.metadata.create_all(bind=engine)
except Exception as e:
    syslog.syslog(syslog.LOG_ERR, f"Error while connecting to the database: {str(e)}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while connecting to the database: {str(e)}")
        raise
    finally:
        db.close()

class Task(BaseModel):
    taskId: int = None
    taskName: str = None
    taskDescription: str = None
    taskDeadline: datetime.date = None
    taskPriority: int = None
    taskStatus: int = 0

    model_config = {
        "from_attributes": True
    }

# -------------------------------Authentication--------------------------------

USER_ID = None

COGNITO_REGION = 'us-east-1'
USER_POOL_ID = 'us-east-1_JlC5VFh6U'
CLIENT_ID = '3fakplt730ef8nvvnd9oj2l6dv'
COGNITO_DOMAIN = 'https://es-todolist.auth.us-east-1.amazoncognito.com'
REDIRECT_URI = 'http://localhost:8000/callback'
# REDIRECT_URI = 'https://es-ua.ddns.net/callback'

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{COGNITO_DOMAIN}/oauth2/authorize",
    tokenUrl=f"{COGNITO_DOMAIN}/oauth2/token",
    scopes={"openid": "OpenID Connect scope"}
)

async def get_current_user(id_token: str = Cookie(None), access_token: str = Cookie(None)):
    if id_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        response = requests.get(f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json")
        jwks = response.json()["keys"]
        payload = jwt.decode(access_token, jwks, algorithms=["RS256"], audience=CLIENT_ID)
        return payload
    except JWTError as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while decoding JWT: {str(e)}")
        raise HTTPException(status_code=403, detail="Not authenticated")


@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 403 or exc.status_code == 401:
        return RedirectResponse(url="/login")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.get("/login")
def login():
    return RedirectResponse(f"{COGNITO_DOMAIN}/login?client_id={CLIENT_ID}&response_type=code&scope=openid&redirect_uri={REDIRECT_URI}")

@app.get("/logout")
def logout():
    return RedirectResponse(f"{COGNITO_DOMAIN}/logout?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code")

@app.get("/callback")
async def callback(code: str, response: RedirectResponse):
    try:
        token_url = f"{COGNITO_DOMAIN}/oauth2/token"
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        token_headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        token_response = requests.post(token_url, data=token_data, headers=token_headers).json()

        if 'id_token' in token_response:
            # Stocker le jeton dans un cookie sécurisé
            response.set_cookie(key="id_token", value=token_response['id_token'], httponly=True, secure=True, samesite="lax")
            response.set_cookie(key="access_token", value=token_response['access_token'], httponly=True, secure=True, samesite="lax")
            response.status_code = 307
            response.headers["location"] = "/"
            return response
        else:
            raise HTTPException(status_code=400, detail="Authentication failed")
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while authenticating: {str(e)}")
        raise HTTPException(status_code=400, detail="Authentication failed")
    

# -------------------------------Routes--------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    try:
        global USER_ID
        USER_ID = user["sub"]

        queryParams = request.query_params
        allTasks = await get_all_tasks(db, user, queryParams)
        print(allTasks)
        tasks = allTasks["tasks"]
        sortBy = allTasks["sortBy"]
        filterBy = allTasks["filterBy"]
        order = allTasks["order"]
        

        # print(tasks)
        return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks, "sortBy": sortBy, "filterBy": filterBy, "order": order, "user": user})
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while getting tasks: {str(e)}")
        return RedirectResponse(url="/login")


@app.get("/get_all_tasks")
async def get_all_tasks(db: Session = Depends(get_db), user: dict = Depends(get_current_user), queryParams: dict = {}):
    try:
        sortBy = queryParams.get("sortBy")
        mapSort = {"Default": TaskModel.id, "Name": TaskModel.taskName, "Priority": TaskModel.taskPriority, "Deadline": TaskModel.taskDeadline, "Completion status": TaskModel.taskStatus}

        order = queryParams.get("order")
        order = "" if order is None else order

        if sortBy in mapSort:
            if order == "desc":
                tasks = db.query(TaskModel).filter(TaskModel.userId == USER_ID).order_by(mapSort[sortBy].desc()).all()
            else:
                tasks = db.query(TaskModel).filter(TaskModel.userId == USER_ID).order_by(mapSort[sortBy]).all()
        else:
            if order == "desc":
                tasks = db.query(TaskModel).filter(TaskModel.userId == USER_ID).order_by(TaskModel.id.desc()).all()
            else:
                tasks = db.query(TaskModel).filter(TaskModel.userId == USER_ID).order_by(TaskModel.id).all()

        filterBy = queryParams.get("filterBy")
        if filterBy:
            filterBy = filterBy.split()
            print(f"Filter by: {filterBy}")

            filters = [TaskModel.userId == USER_ID]

            status_filters = []
            priority_filters = []

            for f in filterBy:
                if f == "completed":
                    status_filters.append(TaskModel.taskStatus == 1)
                elif f == "uncompleted":
                    status_filters.append(TaskModel.taskStatus == 0)
                elif f == "high":
                    priority_filters.append(TaskModel.taskPriority == 3)
                elif f == "medium":
                    priority_filters.append(TaskModel.taskPriority == 2)
                elif f == "low":
                    priority_filters.append(TaskModel.taskPriority == 1)

            if status_filters:
                filters.append(or_(*status_filters))

            if priority_filters:
                filters.append(or_(*priority_filters))

            tasks = db.query(TaskModel).filter(*filters).order_by(TaskModel.id).all()
        else:
            filterBy = []

        return {"tasks": tasks, "sortBy": sortBy, "filterBy": filterBy, "order": order}
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while getting tasks: {str(e)}")
        return {"status": "error"}

@app.post("/add_task")
async def add_task(task: Task, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    print(f"Nom: {task.taskName}, Description: {task.taskDescription}, Deadline: {task.taskDeadline}, Priorité: {task.taskPriority}")

    try:
        newTask = TaskModel(taskName=task.taskName, taskDescription=task.taskDescription, taskDeadline=task.taskDeadline, taskPriority=task.taskPriority, taskStatus=task.taskStatus, userId=USER_ID)
        db.add(newTask)
        db.commit()
        db.refresh(newTask)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while adding task: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)})
    
@app.post("/edit_task")
async def edit_task(task: Task, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    print(f"Id: {task.taskId}, Nom: {task.taskName}, Description: {task.taskDescription}")

    try:
        db.query(TaskModel).filter(TaskModel.id == task.taskId).update({"taskName": task.taskName, "taskDescription": task.taskDescription, "taskDeadline": task.taskDeadline, "taskPriority": task.taskPriority})
        db.commit()
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while editing task: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)})
    
@app.post("/delete_task")
async def delete_task(task: Task, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    print(f"Id: {task.taskId}")

    try:
        db.query(TaskModel).filter(TaskModel.id == task.taskId).delete()
        db.commit()
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while deleting task: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.post("/change_status")
async def change_status(task: Task, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    print(f"Id: {task.taskId}, Status: {task.taskStatus}")

    try:
        db.query(TaskModel).filter(TaskModel.id == task.taskId).update({"taskStatus": task.taskStatus})
        db.commit()
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, f"Error while changing status: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)})
