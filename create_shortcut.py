#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
아이콘(.ico) 생성 + 바로가기(.lnk) 생성
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 아이콘 생성 ────────────────────────────────────────────

def draw_shield(draw, size, fill, stroke):
    """방패 모양 그리기"""
    p = size // 10          # 여백
    r = size // 5           # 상단 모서리 반경
    mid_y = int(size * 0.60)

    # 상단 둥근 사각형
    draw.rounded_rectangle([p, p, size-p, mid_y+r], radius=r, fill=fill)
    # 하단 삼각형 (뾰족)
    tip = [(p, mid_y), (size-p, mid_y), (size//2, size-p)]
    draw.polygon(tip, fill=fill)

    # 외곽선
    draw.rounded_rectangle([p, p, size-p, mid_y+r], radius=r,
                            fill=None, outline=stroke,
                            width=max(2, size//28))
    draw.polygon(tip, fill=None, outline=stroke)

    # 중앙 "D" 글자
    font_size = size * 42 // 100
    font = None
    for path in ["C:/Windows/Fonts/arialbd.ttf",
                 "C:/Windows/Fonts/arial.ttf",
                 "C:/Windows/Fonts/verdana.ttf"]:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except Exception:
            pass

    cx, cy = size // 2, int(size * 0.42)
    try:
        draw.text((cx, cy), "D", fill=stroke, anchor="mm", font=font)
    except TypeError:
        draw.text((cx - font_size//3, cy - font_size//2), "D", fill=stroke)


def make_frame(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 배경 원
    pad = max(1, size // 14)
    draw.ellipse([pad, pad, size-pad-1, size-pad-1], fill=(22, 22, 36, 255))
    # 방패
    s_pad = size // 8
    draw_shield(draw,
                size - s_pad * 2,
                fill=(40, 40, 60, 255),
                stroke=(80, 250, 123, 255))
    # 방패 이미지를 원 위에 합성
    shield_img = Image.new("RGBA", (size - s_pad*2, size - s_pad*2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shield_img)
    draw_shield(sd, size - s_pad*2,
                fill=(40, 40, 60, 255),
                stroke=(80, 250, 123, 255))
    img.paste(shield_img, (s_pad, s_pad), shield_img)
    return img


def create_ico(out_path: str):
    sizes  = [256, 128, 64, 48, 32, 16]
    frames = [make_frame(s) for s in sizes]
    frames[0].save(
        out_path, format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"[OK] 아이콘 생성: {out_path}")
    return out_path

# ── 바로가기 생성 ──────────────────────────────────────────

def create_shortcut(ico_path: str):
    import win32com.client   # pywin32 필요
    lnk_path = os.path.join(BASE, "DisplayGuard 시작.lnk")
    target   = os.path.join(BASE, "start.bat")

    shell    = win32com.client.Dispatch("WScript.Shell")
    lnk      = shell.CreateShortCut(lnk_path)
    lnk.Targetpath       = target
    lnk.WorkingDirectory = BASE
    lnk.IconLocation     = f"{ico_path}, 0"
    lnk.Description      = "DisplayGuard - 멀티모니터 디스플레이 위치 보호"
    lnk.WindowStyle      = 7   # 최소화 상태로 실행 (콘솔창 최소화)
    lnk.save()
    print(f"[OK] 바로가기 생성: {lnk_path}")


def create_shortcut_via_ps(ico_path: str):
    """pywin32 없을 때 PowerShell로 대체"""
    import subprocess
    lnk_path = os.path.join(BASE, "DisplayGuard 시작.lnk")
    target   = os.path.join(BASE, "start.bat")

    ps = f"""
$s = New-Object -ComObject WScript.Shell
$lnk = $s.CreateShortcut('{lnk_path}')
$lnk.TargetPath = '{target}'
$lnk.WorkingDirectory = '{BASE}'
$lnk.IconLocation = '{ico_path}, 0'
$lnk.Description = 'DisplayGuard - 멀티모니터 디스플레이 위치 보호'
$lnk.WindowStyle = 7
$lnk.Save()
"""
    result = subprocess.run(["powershell", "-Command", ps], capture_output=True)
    if result.returncode == 0:
        print(f"[OK] 바로가기 생성: {lnk_path}")
    else:
        print(f"[ERR] 바로가기 생성 실패: {result.stderr.decode('utf-8', errors='ignore')}")


# ── 메인 ──────────────────────────────────────────────────

if __name__ == "__main__":
    ico = create_ico(os.path.join(BASE, "icon.ico"))

    try:
        import win32com.client
        create_shortcut(ico)
    except ImportError:
        create_shortcut_via_ps(ico)
