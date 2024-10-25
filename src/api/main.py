from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from databases import Database

import datetime

USER_ID = 1 #Simuler un utilisateur connecté

Base = declarative_base()
DATABASE_URL = "sqlite:///./database.db"

class User(Base):
    __tablename__ = "User"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

class TaskModel(Base):
    __tablename__ = "Task"
    id = Column(Integer, primary_key=True, index=True)
    userId = Column(Integer, ForeignKey("User.id"))
    taskName = Column(String)
    taskDescription = Column(String, nullable=True)
    taskPriority = Column(Integer, nullable=True)
    taskStatus = Column(Integer, nullable=True)
    taskDeadline = Column(DateTime, nullable=True)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

database = Database(DATABASE_URL)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Task(BaseModel):
    taskId: int = None
    taskName: str = None
    taskDescription: str = None
    taskDeadline: datetime.date = None
    taskPriority: int = None
    taskStatus: int = 0

templates = Jinja2Templates(directory="../html")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    queryParams = request.query_params
    sortBy = queryParams.get("sortBy")
    mapSort = {"Default": TaskModel.id, "Name": TaskModel.taskName, "Priority": TaskModel.taskPriority, "Deadline": TaskModel.taskDeadline, "Completion status": TaskModel.taskStatus}

    if sortBy in mapSort:
        tasks = db.query(TaskModel).filter(TaskModel.userId == USER_ID).order_by(mapSort[sortBy]).all()
    else:
        tasks = db.query(TaskModel).filter(TaskModel.userId == USER_ID).order_by(TaskModel.id).all()
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks, "sortBy": sortBy})

@app.post("/add_task")
async def add_task(task: Task, db: Session = Depends(get_db)):
    print(f"Nom: {task.taskName}, Description: {task.taskDescription}, Deadline: {task.taskDeadline}, Priorité: {task.taskPriority}")

    try:
        newTask = TaskModel(taskName=task.taskName, taskDescription=task.taskDescription, taskDeadline=task.taskDeadline, taskPriority=task.taskPriority, taskStatus=task.taskStatus, userId=USER_ID)
        db.add(newTask)
        db.commit()
        db.refresh(newTask)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})
    
@app.post("/edit_task")
async def edit_task(task: Task, db: Session = Depends(get_db)):
    print(f"Id: {task.taskId}, Nom: {task.taskName}, Description: {task.taskDescription}")

    try:
        db.query(TaskModel).filter(TaskModel.id == task.taskId).update({"taskName": task.taskName, "taskDescription": task.taskDescription, "taskDeadline": task.taskDeadline, "taskPriority": task.taskPriority})
        db.commit()
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})
    
@app.post("/delete_task")
async def delete_task(task: Task, db: Session = Depends(get_db)):
    print(f"Id: {task.taskId}")

    try:
        db.query(TaskModel).filter(TaskModel.id == task.taskId).delete()
        db.commit()
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

@app.post("/change_status")
async def change_status(task: Task, db: Session = Depends(get_db)):
    print(f"Id: {task.taskId}, Status: {task.taskStatus}")

    try:
        db.query(TaskModel).filter(TaskModel.id == task.taskId).update({"taskStatus": task.taskStatus})
        db.commit()
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})
