FROM node:20-alpine

WORKDIR /app/examples/minimal-fastapi-react/frontend

COPY react /app/react
COPY examples/minimal-fastapi-react/frontend/package*.json ./
RUN npm install

COPY examples/minimal-fastapi-react/frontend ./

ENV ROUTEDECK_BACKEND_URL=http://routedeck-backend:8096
EXPOSE 5190
CMD ["npm", "run", "dev"]
