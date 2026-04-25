# Docker 설정 가이드

## 1. Docker Desktop 실행

**Windows에서:**
1. 작업 표시줄에서 Docker Desktop 아이콘 찾기
2. 아이콘을 클릭하거나 시작 메뉴에서 "Docker Desktop" 실행
3. Docker가 완전히 시작될 때까지 대기 (고래 아이콘이 정상 상태가 됨)

**Docker Desktop이 설치되지 않았다면:**
- https://www.docker.com/products/docker-desktop/
- Windows용 설치 파일 다운로드 및 설치
- 설치 후 재부팅 필요할 수 있음

## 2. Docker 실행 확인

```bash
docker --version
docker ps
```

둘 다 에러 없이 실행되면 OK!

## 3. 프로젝트 실행

```bash
# 백엔드 + OpenWebUI 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

## 4. 접속

- **Backend API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **테스트 UI**: http://localhost:8000/test
- **OpenWebUI**: http://localhost:3000

## Docker 없이 실행 (대안)

Docker 없이도 실행 가능해요:

```bash
# 백엔드만 실행
python backend/main.py

# 브라우저에서
# http://localhost:8000/test
```
