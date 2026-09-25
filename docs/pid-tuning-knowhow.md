# FPV機体のPIDチューニング接続ノウハウ

この文書は、Generated Vehicle Packageを箱庭ドローンPROのPID自動チューニングへ接続するときに確認すべき境界と、初回検証で判明した失敗パターンをまとめます。

PID自動チューニングのrunner、探索、評価、結果生成を利用するには、有効な箱庭ドローンPROライセンスが必要です。評価基準と成果物の正本は、`hakoniwa-drone-pro/pro-docs/control-link/pid-tuning.md`です。

原則として、機体固有の探索範囲と試行結果はこのリポジトリへコミットしません。これらは生成機体の質量、慣性、推進系、制御周期に依存するため、Drone PROの無視対象profileと`build/`内で管理します。例外として、人間が飛行確認まで完了した固定PIDは、対応する物理モデルおよび実行設定と分離しない形で`verified-configs/`へ保存できます。PID値だけを別機体へ流用してはいけません。

## 箱庭ドローンPROを利用するメリット

FPV機体は部品構成を変えると、質量、慣性、推力、応答特性が変わります。固定された汎用PIDを配るだけでは、「組み合わせた機体に合うか」を説明できません。

箱庭ドローンPROのPID自動チューニングを接続すると、次の流れを機体ごとに実行できます。

```text
Catalogから部品を選ぶ
  -> 仮想機体と物理特性を生成する
  -> その機体専用の入力profileを固定する
  -> HoverとAngleの候補を自動探索・定量評価する
  -> 波形とhard gateを人間がレビューする
  -> PS5で操縦感を確認する
```

具体的なメリットは次のとおりです。

- 手作業でゲインを一つずつ変更する試行回数を減らせる
- 機体ごとに同じ評価条件で候補を比較できる
- Hover成立、姿勢応答、位相遅れ、軸間干渉などを数値と波形で確認できる
- 入力モデルをhash付きprofileとして固定し、別機体の結果を誤適用しにくい
- 自動探索結果を無条件に採用せず、hard gateと人間のレビューを組み合わせられる
- Catalog変更から再生成・再調整までを一つの設計ループとして扱える

初回のサンプル機体でも、生成時の初期値では安定しなかったAngle飛行を、物理接続の問題を切り分けた上で、Hover、Angle、自動評価、PS5確認の順に成立させられました。これはPID値そのものよりも、異なるFPV機体へ繰り返し適用できる調整工程を確認できたことに価値があります。

したがって、このリポジトリ単体は「機体を構成して生成する基盤」、箱庭ドローンPROは「生成した機体を評価し、調整候補を得るための実行・チューニング基盤」という製品境界です。

## 推奨する順序

Angleモードは現在のDrone PROでは`AttiHover`として動作します。Angleだけを単独で調整せず、次の順序で進めます。

```text
Generated Vehicle Packageを固定
  -> tuning専用ControllerでHoverを成立させる
  -> hard gateと波形を人間が確認する
  -> Hover結果を基準にAngleを調整する
  -> Angleのhard gateと波形を人間が確認する
  -> PS5による実操作で最終確認する
```

物理モデルを変更した場合は、古い結果を流用せず、新しいprofileを作成します。

## 初回検証でつまずいた点

### 通常飛行用Controllerではチューニング入力を受けない

PS5飛行用Packageは`RadioController`を使用します。一方、オフラインPID runnerは`TuningController`を必要とします。通常PackageのControllerを直接書き換えると、PS5飛行との境界が崩れます。

`tune-prepare`は無視対象の作業コピーだけをCSV loggingと`TuningController`へ変更します。通常の生成物は`RadioController`のまま維持します。

### 地上静止をHover成功と誤判定し得る

ローター指令が出ていない機体でも、地面の上では速度と姿勢が安定して見えます。RMS値が小さいことだけではHover成立を保証できません。

確認時は、少なくとも次を見ます。

- TuningControllerがロードされている
- ローター指令が出ている
- 機体が地面を離れている
- 規定のHover高度へ到達している
- Hover判定区間が離陸後に始まっている
- 地面との接触で姿勢が固定されていない

### MuJoCoとDrone PROの座標系を混同しない

生成物の接続では次の変換が必要です。

- MuJoCoはZ-up、Drone PROの初期位置はNED表現
- MuJoCo `Z=+h` に対応するDrone PRO初期位置は `Z=-h`
- Resolved VehicleのMuJoCoローター位置から、Drone PROの`thruster.rotorPositions`へ出力するときはY符号を反転する
- ローター番号、位置、回転方向の対応関係は変えない

符号またはローター対応が誤っていると、PID調整では補償できず、離陸直後に姿勢が発散します。PIDを疑う前に、座標とMixerの対応を検証します。

### 大型機の探索範囲をFPV機へそのまま適用しない

小型FPV機は大型の基準機より慣性が小さく、同じゲインでは過敏になり得ます。既存機体向けの固定ゲインや探索範囲は、互換性のある初期値ではありません。

探索範囲を決める前に、生成された質量、各軸慣性、最大推力、推力重量比、制御周期を確認します。発散する場合は、物理接続に問題がないことを確認した上で、低いRateゲイン側から探索します。

### プロセス終了コードだけで成功判定しない

自動チューニングのパイプラインは、試験や採用判定が失敗しても、処理自体が完了すれば終了コード0になる場合があります。

`tools/fpv.py`は`pipeline-report.json`を読み、`status`と`failed_phase`を確認します。CLIが終了したことと、採用可能な候補が得られたことを区別します。

### best candidateは採用決定ではない

スコア最大の候補でも、hard gate、波形、飽和、振動、軸間干渉を人間が確認する必要があります。数値評価を通過した後も、PS5操作で次を確認します。

- スティック中央付近で姿勢が落ち着く
- Roll/Pitch指令に対して過大な振動や発散がない
- 指令を戻したときに不自然な残留振動がない
- Yaw操作がRoll/Pitchを大きく乱さない
- スロットル操作と姿勢制御が同時に成立する

## チューニング前チェックリスト

- `drone.xml`がMuJoCoでロードできる
- MuJoCo初期高度とDrone PRO NED初期位置の符号が対応している
- ローター番号、座標、回転方向、Mixerの対応が一致している
- 質量、慣性、Ct/Cq、最大回転数に根拠または明示した近似がある
- 通常飛行は`RadioController`、tuning作業コピーは`TuningController`になっている
- tuning作業コピーではCSV loggingが有効になっている
- tuning作業コピーの初期高度が2 mで、地面に支持された静止をHoverとして評価しない
- 物理モデル、制御周期、シミュレーション周期をprofile作成後に変更していない
- profileが入力3ファイルのhashで識別されている

`python3.12 tools/fpv.py tune-audit`は上記のうち、質量・MuJoCo剛体値・`MASS`、`Ct`の二重定義、ローター数・位置・回転方向を機械的に照合する。MuJoCoの`inertiafromgeom`を使うGenerated Packageでは、`drone_config_0.json`の`inertia: [0, 0, 0]`は「MuJoCoへ委譲」を表す。この場合も、監査結果JSONにはMuJoCoが算出したCOMと慣性対角値を残す。

## 実行と確認

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py tune-build
python3.12 tools/fpv.py tune-audit
python3.12 tools/fpv.py tune-prepare
python3.12 tools/fpv.py tune-hover
```

Hoverのhard gate、離陸成立、波形を確認してから進みます。

Hoverでは姿勢系を探索しません。Rate Kp/Ki/Kdを`0.15/0.08/0.005`、Angle Kp/Ki/Kdを`6/0.5/0.75`へ固定し、垂直速度PIDだけを探索します。これは地面上では合格してしまう高ゲイン候補を排除し、まず自由空間で維持できる高度系を確立してからAngle探索へ進むためです。高度2 mからの自由空間開始では初期Pitch過渡に約3.5秒を要する実測結果に基づき、Hover entry hard gateはFPV profile内で5秒とします。

```bash
python3.12 tools/fpv.py tune-angle --angle-trials 40 --angle-refine
python3.12 tools/fpv.py tune-apply
python3.12 tools/fpv.py start
```

Drone PRO標準hard gateの後、FPV側は各trialを次の条件で再判定します。

- 評価区間の最低高度が0.1 m以上
- 評価区間中に接触回数が増えない
- Motor Dutyが0または1へ張り付くサンプルの比率が10%以下

条件を満たすtrialのうちスコアが最も高い候補だけが`pid-tuning-<phase>-selected-params.json`へ保存されます。`tune-apply`はAngleの選択結果を`build/<package>/runtime/vehicle/control-param.txt`へ一時適用します。Catalog、Recipe、生成時の初期制御値は変更しません。`configure`を再実行すると生成初期値へ戻ります。

Angle候補を選択した後は、そのPIDを使って地面ありのMuJoCoモデル上で最終Hover検証を行います。初期高度2 m、試験時間15秒とし、2秒後から10秒以上、垂直速度±0.15 m/s、Roll/Pitch±2度を維持することに加え、最低高度、接触、Motor Duty飽和のFPV flight gateを通過しなければなりません。この結果は`pid-tuning-post-angle-hover.json`へ保存されます。

## この手順が保証しないこと

- シミュレーション用PID値が実機へそのまま適用できること
- Catalog値や推進モデルが実機を十分な精度で再現していること
- Betaflight互換のフィルタ、Feedforward、Dynamic Notch等の挙動
- すべての飛行領域やバッテリー状態における安定性

CatalogとRecipeから生成したFPV機体をDrone PRO PID調整経路へ接続し、Drone PRO標準評価とFPV flight gateの両方を通過した候補だけをPS5確認へ進めます。
