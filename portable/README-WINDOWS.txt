Hakoniwa FPV Drone (Master3X) - Windows Portable

1. このフォルダを任意の場所へ展開してください（パスは短いほうが安全です。例: C:\hakoniwa-fpv）。
2. PS5 コントローラ（DualSense）を Windows に接続してください。
3. start-fpv-drone.bat をダブルクリックしてください。
   初回と、フォルダを移動したあとの最初の起動では、機体設定の生成に少し時間がかかります。
   起動が終わると、ブラウザに Three.js のビューアが開きます。
4. 操縦の手順
   - × ボタンを押して離す: Radio Control を有効にします。
   - △ ボタンを押して離す: ATTI モードに切り替えます。
   - 左スティックを上げる: 浮上します。
   × と △ は押すたびに切り替わります。状態は status-fpv-drone.bat で確認できます。
5. 終了するときは stop-fpv-drone.bat を実行してください。

Python / Git / WSL / Docker / C++ ビルド環境のインストールは不要です。

うまく動かないとき
- "no game controller is connected": コントローラを接続してから、もう一度 start してください。
- "port ... is in use": 表示されたプロセスを終了してから、もう一度 start してください。
- "in use by another Hakoniwa simulation": 別の箱庭シミュレーションを stop してから start してください。
- 起動直後に DLL が見つからないというエラーが出る場合は、
  Microsoft Visual C++ 再頒布可能パッケージ (x64) をインストールしてください。
- ログ: hakoniwa-fpv-drone\build\portable-master3x\runtime\logs
