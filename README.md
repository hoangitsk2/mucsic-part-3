# Raspberry Pi Recess Music Automation

Dự án này giúp Raspberry Pi tự động phát nhạc vào giờ ra chơi và tự tắt nguồn khi kết thúc. Phần mềm có thể tự chạy khi Pi khởi động, hỗ trợ nhiều lịch phát khác nhau trong ngày, có giao diện web đơn giản để điều khiển thủ công và có thể tải nhạc từ YouTube.

## Tính năng chính

- Đọc cấu hình lịch phát từ `config.json`.
- Phát playlist trong thư mục `playlist/` theo thứ tự.
- Tự động tắt Raspberry Pi bằng lệnh `sudo shutdown now` sau mỗi phiên phát (có thể bật/tắt theo từng lịch).
- Giao diện web (Flask) để:
  - Xem trạng thái hiện tại, danh sách lịch và playlist.
  - Bật/tắt phát nhạc thủ công.
  - (Tuỳ chọn) gọi API tải nhạc từ YouTube bằng `yt-dlp`.
- Có thể cấu hình nhiều lịch ra chơi trong ngày.
- Hỗ trợ chạy nền khi bật máy bằng systemd service hoặc `cron @reboot`.

## Cấu trúc thư mục

```
├── app.py                    # Điểm chạy chính, gồm scheduler + Flask
├── config.json               # Thời gian ra chơi, thời lượng, cấu hình web
├── playlist/                 # Lưu các file .mp3, .wav, .ogg
├── utils/
│   ├── music_player.py       # Điều khiển phát nhạc bằng pygame
│   └── youtube_downloader.py # Tải audio từ YouTube bằng yt-dlp
├── templates/index.html      # Giao diện web
├── static/style.css          # CSS giao diện
└── logs/                     # Thư mục chứa file log khi chạy thật
```

## Yêu cầu hệ thống

- Raspberry Pi OS (Debian-based)
- Python 3.9+
- Loa hoặc ampli kết nối Pi
- Các thư viện Python: `flask`, `schedule`, `pygame` (hoặc `python-vlc` nếu muốn tự chỉnh), `yt-dlp`

Cài đặt nhanh:

```bash
sudo apt update && sudo apt install python3 python3-pip ffmpeg
pip3 install flask schedule pygame yt-dlp
```

## Cấu hình `config.json`

```json
{
  "music_directory": "playlist",
  "log_file": "logs/app.log",
  "schedules": [
    {
      "label": "Morning Recess",
      "start_time": "09:30",
      "duration_minutes": 15,
      "shutdown_after": true
    },
    {
      "label": "Afternoon Recess",
      "start_time": "15:00",
      "duration_minutes": 10,
      "shutdown_after": true
    }
  ],
  "web": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 5000
  },
  "shutdown_command": "sudo shutdown now",
  "youtube": {
    "audio_format": "mp3"
  }
}
```

- `start_time` dùng định dạng 24h `HH:MM`.
- `duration_minutes` là thời lượng phát nhạc, kết thúc sẽ chạy lệnh shutdown nếu `shutdown_after = true`.
- Bạn có thể thêm nhiều lịch hơn bằng cách thêm phần tử vào mảng `schedules`.
- Nếu không muốn giao diện web, đặt `"enabled": false` hoặc chạy `python app.py --no-web`.

## Chạy ứng dụng

```bash
python3 app.py
```

Hoặc chỉ chạy scheduler (không web):

```bash
python3 app.py --no-web
```

Ứng dụng sẽ:

1. Đọc `config.json`.
2. Đăng ký lịch với thư viện `schedule`.
3. Đến giờ, phát nhạc từ thư mục `playlist/` theo thứ tự file.
4. Sau khi hết thời lượng, nếu `shutdown_after = true`, chạy `sudo shutdown now` để tắt Pi.

## Thiết lập auto-start bằng systemd

Tạo file service `/etc/systemd/system/recess-music.service`:

```ini
[Unit]
Description=Recess Music Automation
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/recess-music
ExecStart=/usr/bin/python3 /home/pi/recess-music/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Kích hoạt dịch vụ:

```bash
sudo systemctl daemon-reload
sudo systemctl enable recess-music.service
sudo systemctl start recess-music.service
```

## Tuỳ chọn cron @reboot

Nếu không muốn systemd, thêm vào `crontab -e` của user `pi`:

```
@reboot /usr/bin/python3 /home/pi/recess-music/app.py >> /home/pi/recess-music/logs/cron.log 2>&1
```

## Tự động tắt Raspberry Pi

Ứng dụng sẽ gọi `sudo shutdown now` sau khi phát nhạc xong. Đảm bảo user chạy service có quyền không cần nhập mật khẩu:

```bash
sudo visudo
```

Thêm dòng:

```
pi ALL=(ALL) NOPASSWD: /sbin/shutdown
```

## Thêm nhạc

- Sao chép file `.mp3` vào thư mục `playlist/`.
- Hoặc dùng API tải nhạc từ YouTube:

```bash
curl -X POST http://<pi-ip>:5000/download \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

File sẽ được tải vào `playlist/` với định dạng do `audio_format` quy định.

## Giao diện web

Truy cập `http://<pi-ip>:5000/` để xem trạng thái, lịch và playlist. Tại đây có thể:

- Nhập thời lượng (phút) và bắt đầu phát thủ công (không tắt máy sau khi xong).
- Bấm “Stop Playback” để dừng ngay lập tức.

## Ghi log

Mặc định log ghi vào `logs/app.log` và đồng thời in ra console. Có thể thay đổi đường dẫn trong `config.json`.

## Mở rộng

- Có thể thay `pygame` bằng `python-vlc` hoặc `omxplayer` nếu muốn.
- Thêm xác thực cho giao diện web.
- Thêm tính năng upload file trực tiếp.
- Tích hợp MQTT để nhận tín hiệu phát nhạc từ thiết bị khác.

## Cảnh báo

Lệnh `sudo shutdown now` sẽ tắt Raspberry Pi ngay lập tức. Kiểm tra kỹ trước khi chạy trên máy thật.
