from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
  """Extend Django AbstractUser"""
  email = models.EmailField(unique=True)
  
  # extend later
  
  USERNAME_FIELD = 'email'
  REQUIRED_FIELDS = ['username']  

  def __str__(self):
    return self.username or self.email