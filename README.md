# HIDClaw

![project banner](docs/images/banner.png)



### これは何だ？



PCに接続すると、外部ディプレイとキーボード/マウスとして認識されます。
しかしその実態はHDMIキャプチャーデバイスとHIDデバイスで、キャプチャーしたスクリーン画像からComputer Use API呼び出し、PCの操作コマンドを生成し、HIDデバイス経由でキーボード/マウス操作を送り込み、PCを物理的に操作する、というAI**デバイス**です。

Raspberry Pi 5、Raspberry Pi Pico / Pico 2を用意して、下記のセットアップを行い、操作したいPCに接続すると利用できます。



変更履歴：

- Version1.1: エージェントの意図理解と操作計画を強化しました。



## デモンストレーション動画

[動作動画を見る](https://youtu.be/BOC1nILZCNE)

動画では、Raspberry Pi 5 上の WebUI から PC 操作リクエストを入力し、画面キャプチャー、Computer Use API 呼び出し、Pico への HID コマンド送信、対象 PC 操作までの流れを確認できます。

## Hardware接続

- Raspberry Pi 5
- Raspberry Pi Pico / Pico 2
- USB HDMI キャプチャーデバイス
- 操作対象 PC

![接続写真](docs/images/connection.png)

```text
対象 PC
├─ HDMI OUT ── USB HDMI Capture Board ── Raspberry Pi 5
└─ USB IN   ── Raspberry Pi Pico / Pico 2

Raspberry Pi 5
├─ HDMI キャプチャーで対象 PC の画面を取得
├─ UART で Pico へ操作コマンドを送信
└─ WebUI / Discord / CLI から操作を受け付け

Raspberry Pi Pico / Pico 2
├─ UART で Pi 5 からコマンドを受信
└─ USB HID Keyboard / Mouse として対象 PC を操作
```

UART 配線:

```text
Raspberry Pi 5 GPIO14 TXD -> Pico GP1 / UART0 RX
Raspberry Pi 5 GPIO15 RXD <- Pico GP0 / UART0 TX
Raspberry Pi 5 GND        <-> Pico GND
```

## 主要な機能

- WebUI から自然言語で対象 PC を操作する
- Plan モードで複数ステップの操作計画を作ってから実行する
- Manual HID で `KEY WIN+R` や `TEXT hello` などの低レベルコマンドを直接送る
- Emergency Stop / Suspend / Resume で操作を止める
- 操作ログ、スクリーンショット、トークン使用量を保存する
- メール通知と Discord からの操作に対応する

## クイックスタート

Pi 5 上で WebUI を起動します。

```sh
python3 pi/app.py --mode web --config config/example.toml
```

ブラウザで開きます。

```text
http://127.0.0.1:8080/
```

詳しい起動方法、設定ファイル、Request / Plan / Manual HID、メール通知、Discord bot の設定は [HOW_TO_USE.md](HOW_TO_USE.md) を参照してください。

## ドキュメント

- [HOW_TO_USE.md](HOW_TO_USE.md): 使い方と設定
- [docs/DISCORD_COMMANDS.md](docs/DISCORD_COMMANDS.md): Discord コマンドのリファレンス
- [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md): 開発仕様
- [docs/TESTING.md](docs/TESTING.md): テスト手順
