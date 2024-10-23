from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from databases import Database

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
    taskDeadline = Column(String, nullable=True)

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

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


class Task(BaseModel):
    taskName: str
    taskDescription: str = None

templates = Jinja2Templates(directory="../html")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)): 
    #Filter les taches en fonction de userid
    tasks = db.query(TaskModel).filter(TaskModel.userId == USER_ID).all()
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks})

@app.post("/add_task")
async def add_task(task: Task, db: Session = Depends(get_db)):
    print(f"Nom: {task.taskName}, Description: {task.taskDescription}")

    try:
        newTask = TaskModel(taskName=task.taskName, taskDescription=task.taskDescription, userId=USER_ID)
        db.add(newTask)
        db.commit()
        db.refresh(newTask)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})

