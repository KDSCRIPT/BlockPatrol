from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    ipfs_hash = Column(String, index=True)
    transaction_hash = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    aptos_address = Column(String, index=True)
    extracted_data = Column(Text)  # JSON string of extracted data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User", back_populates="documents")

# Add relationship to User model
from app.models.user import User
User.documents = relationship("Document", back_populates="user") 