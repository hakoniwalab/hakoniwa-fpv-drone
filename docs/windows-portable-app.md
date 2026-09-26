# Hakoniwa FPV Drone（Master3X）Windowsアプリ 利用ガイド

Master3Xの機体を、PS5コントローラ（DualSense）で操縦し、ブラウザのThree.jsビューアで見るWindows向けアプリです。ZIPを展開して`start-fpv-drone.bat`を実行するだけで動きます。Python・Git・WSL・Docker・C++ビルド環境のインストールは不要です。

アプリの作り方（開発者向け）は、READMEの[Windows配布用ZIP](../README.md#windows配布用zip一般ユーザー向けmaster3x)を参照してください。

## 動作環境

| 項目 | 内容 |
|---|---|
| OS | Windows 11（x64） |
| コントローラ | PS5 DualSense（USBまたはBluetoothでWindowsに接続） |
| ブラウザ | Three.jsビューアを表示できるブラウザ（Microsoft Edge、Google Chromeなど） |
| ディスク | ZIPが約90MB。展開後はこれより大きくなります |
| ネットワーク | 不要です。ローカルのポート`28000`（HTTP）と`28765`（WebSocket）を使います |

起動直後にDLLが見つからないというエラーが出る場合は、[Microsoft Visual C++ 再頒布可能パッケージ（x64）](https://learn.microsoft.com/ja-jp/cpp/windows/latest-supported-vc-redist)をインストールしてください。

## 1. ダウンロードと展開

1. [Releases](https://github.com/hakoniwalab/hakoniwa-fpv-drone/releases)から`hako-fpv-master3x-win64.zip`をダウンロードします。
2. ZIPを右クリックして**すべて展開**を選び、展開します。ZIPを開いたまま（エクスプローラーでZIPの中を見ている状態）では実行できません。
3. 展開先は、`C:\hakoniwa-fpv`のような**短いパス**にしてください。Windowsのパス長の制限（260文字）に引っかかると、起動に失敗します。デスクトップやダウンロードフォルダの深い場所は避けてください。

展開すると、次のファイルがあります。

```text
hako-fpv-master3x-win64\
├── start-fpv-drone.bat      起動
├── status-fpv-drone.bat     状態確認
├── stop-fpv-drone.bat       停止
├── README-WINDOWS.txt       簡易説明
├── portable-package.json    パッケージ情報（作成元のリビジョンなど）
├── hakoniwa-business-pack\
├── hakoniwa-drone-core\
├── hakoniwa-fpv-drone\
├── hakoniwa-pdu-python\
└── hakoniwa-threejs-drone\
```

`.bat`の実行時にWindows SmartScreenの警告が表示された場合は、配布元を確認したうえで**詳細情報**→**実行**を選んでください。

## 2. 起動する

1. PS5コントローラをWindowsに接続します。**コントローラがないと起動しません**。
2. `start-fpv-drone.bat`をダブルクリックします。
3. 起動が終わると、既定のブラウザでThree.jsビューアが開きます。
4. ビューアの左上にある**connect**を押します。表示が`connected`になると、機体の状態が表示され、操縦できる状態になります。

初回の起動と、フォルダを移動したあとの最初の起動では、展開先に合わせて機体設定を生成するため、少し時間がかかります。2回目以降は生成を省きます。

起動に使ったウィンドウは、正常に起動すると閉じます。エラーで止まった場合は、メッセージを表示したまま待ちます。

## 3. 操縦する

1. **×ボタンを押して離す**：Radio Controlが有効になります（アーム）。押し続ける必要はありません。
2. **△ボタンを押して離す**：初期のGPSモードからATTI（Angle）モードに切り替わります。
3. **左スティックを上へ倒す**：浮上します。スティックを中央に戻すと、その高度でホバリングします。

この機体は、**GPSモードのままでは浮上しません**。必ず△でATTIに切り替えてください。

×と△は**押すたびに切り替わるトグル**で、ビューアには状態が表示されません。2回押すと元に戻ります。迷ったら`status-fpv-drone.bat`で状態を確認してください（[4. 状態を確認する](#4-状態を確認する)）。

| スティック | 上下 | 左右 |
|---|---|---|
| 左 | スロットル（上昇・下降） | Yaw（機首の向き） |
| 右 | Pitch（前進・後退） | Roll（左右移動） |

高度0.2m以下で左スティックを下へ倒し続けると、着陸します。

### ビューアの操作

ビューアは、機体に搭載したカメラの主観映像をメインに、自由に動かせる客観映像を左上の小窓（PiP）に表示します。

| キー | 動作 |
|---|---|
| `Tab` | 主観映像と客観映像を入れ替える |
| `F` | 小窓の表示・非表示を切り替える |

## 4. 状態を確認する

`status-fpv-drone.bat`を実行すると、シミュレーションと機体の状態を表示します。

```text
Simulation    : running
Controller    : <接続したコントローラの名前>
Radio Control : ON
Mode          : ATTI
Flight state  : Hovering
```

浮上させるには、`Radio Control : ON`と`Mode : ATTI`になっている必要があります。次にすべき操作がある場合は、`Next:`の行に表示されます。

## 5. 終了する

`stop-fpv-drone.bat`を実行します。ブラウザのタブを閉じただけでは、シミュレーションは止まりません。

フォルダを削除・移動する前にも、必ず`stop-fpv-drone.bat`で停止してください。動作中はファイルが使用中になり、削除できません。

## うまく動かないとき

| 症状・メッセージ | 対処 |
|---|---|
| `no game controller is connected` | コントローラを接続してから、もう一度`start-fpv-drone.bat`を実行してください |
| `port ... is in use` | 表示されたプロセスを終了してから、もう一度startしてください。ポート`28000`と`28765`を使います |
| `in use by another Hakoniwa simulation` | 別の箱庭シミュレーションを停止してから、startしてください |
| `The viewer HTTP server did not start` | 起動の途中でどれかのプロセスが止まっています。`status-fpv-drone.bat`を実行し、下記のログを確認してください |
| DLLが見つからないというエラー | Microsoft Visual C++ 再頒布可能パッケージ（x64）をインストールしてください |
| ビューアに機体の状態が出ない | 左上の**connect**を押したか確認してください |
| 浮上しない | `status-fpv-drone.bat`で`Radio Control : ON`と`Mode : ATTI`を確認してください。×と△はトグルなので、押し直すと元に戻ります |
| ボタンやスティックが反応しない | コントローラがWindowsに認識されているか確認し、stopしてからもう一度startしてください |
| 起動に失敗する（原因不明） | 展開先のパスが長すぎないか確認してください。`C:\hakoniwa-fpv`のような短いパスに展開し直すと解決することがあります |

### ログの場所

各プロセスのログは、次のフォルダに出力されます。問い合わせの際は、このフォルダの中身を添えてください。

```text
hakoniwa-fpv-drone\build\portable-master3x\runtime\logs
```

| ファイル | 内容 |
|---|---|
| `fpv-drone-service.*` | ドローンの物理・制御シミュレーション |
| `fpv-remote-controller.*` | PS5コントローラの入力 |
| `fpv-visual-state-publisher.*` | ビューアに送る機体の状態 |
| `fpv-threejs-web-bridge.*` | ブラウザとのWebSocket通信 |
| `fpv-realtime-pacer.*` | シミュレーション時間を実時間に合わせる処理 |

起動全体の流れは、`hakoniwa-fpv-drone\build\portable-master3x\runtime\launcher-session.json.log`に記録されます。

## ライセンス

同梱する各リポジトリのライセンスは、それぞれのフォルダにある`LICENSE`を参照してください。
