FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY acop_basement/ ./acop_basement/
COPY acop_composer/ ./acop_composer/
COPY config/ ./config/

EXPOSE 8000

# ★이 이미지는 "관리용 빌드"다 — acop_composer 를 포함해 app.entrypoint:app
#   을 띄운다. 고객 대면 전용(Composer 없음) 이미지를 따로 내려면 위
#   COPY acop_composer/ 줄을 빼고 CMD 를
#   uvicorn acop_basement.presentation.api.app:app 으로 바꾼다
#   (docs/handoff/13·14, `docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md`).
# Composer _WRITE_LOCK is process-local; keep one Uvicorn worker.
CMD ["uvicorn", "app.entrypoint:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
