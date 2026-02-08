FROM python:3.10-slim

# הגדרת תיקיית עבודה
WORKDIR /app

# העתקת קבצי הדרישות
COPY requirements.txt .

# התקנת הספריות
RUN pip install --no-cache-dir -r requirements.txt

# העתקת כל שאר הקבצים
COPY . .

# פקודה להרצת הבוט (וודא שזה השם של הקובץ שלך!)
CMD ["python", "casino_bot_fixed (1).py"]
