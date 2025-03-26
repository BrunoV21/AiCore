from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Session(Base):
    __tablename__ = 'Session'
    
    session_id = Column(String, primary_key=True)
    workspace = Column(String)
    agent_id = Column(String)
    
    # Fix: Use lowercase "messages" to match ORM expectations
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = 'Message'
    
    operation_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey('Session.session_id'))
    action_id = Column(String)
    timestamp = Column(String)
    system_prompt = Column(Text)
    user_prompt = Column(Text)
    response = Column(Text)
    assistant_message = Column(Text)
    history_messages = Column(Text)
    completion_args = Column(Text)
    error_message = Column(Text)
    
    # Fix: Use lowercase "session"
    session = relationship("Session", back_populates="messages")
    
    # Fix: Use lowercase "metric"
    metric = relationship("Metric", back_populates="message", uselist=False)

class Metric(Base):
    __tablename__ = 'Metric'
    
    operation_id = Column(String, ForeignKey('Message.operation_id'), primary_key=True)
    operation_type = Column(String)
    provider = Column(String)
    model = Column(String)
    success = Column(Boolean)
    temperature = Column(Float)
    max_tokens = Column(Integer)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    total_tokens = Column(Integer)
    cost = Column(Float)
    latency_ms = Column(Float)
    
    # Fix: Use lowercase "message"
    message = relationship("Message", back_populates="metric")