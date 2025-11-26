# cheeseshirt web

the terminal interface.  noir aesthetic.  typewriter effect.

## setup

```bash
cd web
npm install
```

## docker

build:
```bash
docker build -t cheeseshirt-web .
```

run (requires api container):
```bash
docker run -d -p 80:80 cheeseshirt-web
```

or use docker-compose from project root:
```bash
docker-compose up -d
```

## run

development (with api proxy):
```bash
npm run dev
```

opens at http://localhost:3000

make sure the api is running on port 3001 (configured in `vite.config.ts`).

## build

```bash
npm run build
```

outputs to `./dist` - serve with nginx or any static file server.

## nginx config example

```nginx
server {
    listen 443 ssl http2;
    server_name cheeseshirt.com;

    ssl_certificate /etc/letsencrypt/live/cheeseshirt.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cheeseshirt.com/privkey.pem;

    root /var/www/cheeseshirt/web/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## structure

```
web/
├── index.html          # single page
├── src/
│   ├── main.ts         # terminal behavior
│   └── styles.css      # noir aesthetic
├── vite.config.ts      # dev server + build
└── tsconfig.json       # typescript
```
