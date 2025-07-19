from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Session(Base):
    __tablename__ = 'Session'
    
    session_id = Column(String(255), primary_key=True)  # Specify a fixed length
    workspace = Column(String)
    agent_id = Column(String)
    
    # Fix: Use lowercase "messages" to match ORM expectations
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = 'Message'
    
    operation_id = Column(String(255), primary_key=True)  # Specify a fixed length
    session_id = Column(String(255), ForeignKey('Session.session_id'))
    action_id = Column(String)
    timestamp = Column(String) #TODO in future this will be replaced with DateTime
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
    
    operation_id = Column(String(255), ForeignKey('Message.operation_id'), primary_key=True)  # Specify a fixed length
    operation_type = Column(String)
    provider = Column(String)
    model = Column(String)
    success = Column(Boolean)
    temperature = Column(Float)
    max_tokens = Column(Integer)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cached_tokens = Column(Integer) 
    total_tokens = Column(Integer)
    cost = Column(Float)
    latency_ms = Column(Float)
    extras = Column(Text)
    
    # Fix: Use lowercase "message"
    message = relationship("Message", back_populates="metric")