from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# SQLAlchemy models
class Session(Base):
    __tablename__ = 'Session'
    
    session_id = Column(String, primary_key=True)
    workspace = Column(String)
    agent_id = Column(String)
    
    # Relationships
    messages = relationship("Message", back_populates="session", lazy="selectin")

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
    
    # Relationships
    session = relationship("Session", back_populates="messages", lazy="selectin")
    metrics = relationship("Metric", back_populates="message", uselist=False, lazy="selectin")

class Metric(Base):
    __tablename__ = 'Metric'
    
    operation_id = Column(String, ForeignKey('Message.operation_id'), primary_key=True)
    operation_type = Column(String)
    provider = Column(String)
    model = Column(String)
    success = Column(Boolean)
    temperature = Column(String)
    max_tokens = Column(Integer)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    total_tokens = Column(Integer)
    cost = Column(Float)
    latency_ms = Column(Float)
    
    # Relationships
    message = relationship("Message", back_populates="metrics", lazy="selectin")