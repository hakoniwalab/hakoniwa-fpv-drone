# Generated Vehicle Package

Generated Packageは入力、解決結果、実行成果物、計算根拠を一つにまとめます。

`--world`指定時は、入力World YAMLを`world.yaml`として同梱し、`drone.xml`へ背景、照明、地面、障害物を合成します。機体定義の由来とコース定義の由来は混ぜません。

## 実行成果物

### drone.xml

- `drone_base` free body
- Catalog/Recipeから計算したmass、center of mass、diagonal inertia
- Quad Xの `prop1`〜`prop4`
- frameのbox proxy
- FPV camera geomとMuJoCo camera
- `--world`指定時の明るいskybox、照明、地面、FPVゲート等

### drone_config.json

現在のDrone PRO単機PDU定義に合わせ、実行時robot名は`Drone`です。Recipeの機体名は`recipe.yaml`、`resolved-components.yaml`、`report.json`に保持されます。

Drone PRO既存形式です。主要な接続点は次の通りです。

- `physicsEquation: MuJoCo`
- `mujoco.modelPath: drone.xml`
- `mujoco.modelName: drone_base`
- MuJoCo `Z=+0.25 m` に対応するDrone PRO初期位置: NED `Z=-0.25 m`
- `rotor.dynamics_constants`: Motor/Propeller Catalog由来
- `thruster.rotorPositions`: Resolved VehicleのMuJoCo座標から、Drone PRO機体座標へY符号を反転して生成
- `controller.backendType: adapter-hakoniwa`
- `controller.paramFilePath: control-param.txt`

### control-param.json / control-param.txt

JSONは設計・調整・将来tuning連携用の正本です。各値にoriginを保持します。TXTは現行Drone PROのruntime adapterです。

```text
control-param.json + generated model
       ↓ Drone PRO existing PID tuning
tuned control parameters
       ↓
新しいVehicle Package revision
```

`tools/fpv.py tune-prepare`は、実行用Packageの`drone_config_0.json`、`drone.xml`、`control-param.txt`を入力としてDrone PROの自己完結profileを生成します。無視対象の作業コピーだけをCSV loggingと`TuningController`へ変更し、通常のPS5実行Packageは`RadioController`のまま維持します。3ファイルのSHA-256をprofile識別子へ含めるため、物理モデルを変更した後に古い調整結果を誤って継続利用しません。

PID自動チューニングのrunner、探索、評価、結果生成は箱庭ドローンPROの機能であり、その実行には有効な箱庭ドローンPROライセンスが必要です。

## 検証済みDrone Configの復元

`verified-configs/example-5inch-angle/drone-config/`には、2026-08-29にPS5 Angle飛行で確認したサンプル機体の`drone.xml`、`drone_config_0.json`、`control-param.txt`を固定しています。PID調整profile、探索空間、試行ログはDrone PROライセンス対象の作業情報であり、ここには含めません。

`configure`はCatalogとRecipeから生成した後、RecipeとWorldのpathおよびSHA-256がReceiptと一致すれば、検証済み3ファイルを自動適用します。したがって通常手順は次のとおりです。

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py start
```

未調整の生成初期値を意図的に調べる場合だけ`configure --generated-defaults`を使用します。`restore-verified-config`は、既存Runtimeへ検証済み構成を明示的に戻す保守用コマンドとして残しています。

Git上の`drone_config_0.json`は移植可能な`modelPath: drone.xml`を保持します。適用時に対象Runtimeの絶対パスへ変換されるため、clone先のディレクトリには依存しません。検証条件とファイルhashは`verified-configs/example-5inch-angle/receipt.json`を参照してください。

現在のAngle実行Profileは高度方向に`AttiHover`を使うため、調整順序は必ずHover、目視レビュー、Angleです。チューナー、評価、探索範囲、採用判定の正本はDrone PRO側にあり、本リポジトリは入力を接続するだけです。

FPV機体をこの経路へ接続するときの事前確認と既知の失敗パターンは、[PIDチューニング接続ノウハウ](pid-tuning-knowhow.md)を参照してください。

FPV Launcherは、FPV側の`fpv_rc_bootstrap.py`でGameController PDUをニュートラル値として初期化してから、Drone PRO標準の`rc-custom.py`へ処理を引き渡します。起動直後の未初期化PDUと最初のPS5ボタン操作が競合してもDrone PRO本体を変更しないためのランタイム境界です。

## report.jsonの状態

- `calculated`: CatalogとRecipeから直接計算
- `approximation`: 明記した物理近似を使用
- `estimate`: Catalog係数に基づく性能推定
- `not_calculated`: 必要なモデルがなく、値を生成していない

MVPでは飛行時間を未計算としてnullにします。適当な消費電流を置いて数値だけ埋めることはしません。

## MuJoCo Viewer

MuJoCo Python bindingがある場合:

```bash
python -m mujoco.viewer --mjcf build/example-5inch/drone.xml
```

単体Viewer確認はモデル形状の確認であり、Drone PROのRotor/Mixer制御まで確認するものではありません。`tools/fpv.py start`で起動するDrone PRO Viewerは、機体固定`fpv`カラを全面、操作可能な客観カラを左上PiPとして表示します。
