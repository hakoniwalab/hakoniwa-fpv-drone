# 部品Catalogの外観再現に必要な入力情報と受入要件

## 目的と対象精度

Master3XのComposer表示改善（`1c86dc4`）を基準に、次の製品追加でも同程度の
外観を再現するための入力要件を定める。対象は「製品の特徴が分かり、部品を
組み立てた外観を営業デモで確認できる」精度である。製造用CADの寸法精度や、
写真と区別できない画質、実機の飛行性能の再現を達成したという意味ではない。

URLは資料の入口であり、それだけで形状を定義できるわけではない。
**製品・構成の特定、複数方向の画像、寸法の基準、取付位置、比較用の完成写真**が
揃って初めて、根拠のある外観モデルを作れる。値が不明でも近似は作れるが、
不明部分を含む精度保証はできない。

## 今回分かったこと

最初のMaster3X登録では、製品名・基本スペック・接続情報が揃っていても、
表示形状は平板のFrame、円柱のMotor、円盤のPropellerだった。
データ読み込みとGLB生成のテストには合格したが、期待された外観ではなかった。

複数方向の完成写真と部品ページを参照して、次を追加すると識別しやすくなった。

- 3枚の独立した羽根とハブ。
- 細長い積層プレート、上板の開口、支柱、黄色い側板とモーターフット。
- Motorのベル開口と内部の色分け。
- 前方のレンズ・保護枠・放熱部・アンテナと、上面のBattery・ベルト・配線。

これはMuJoCoの描画能力の改善ではなく、入力した表示形状の改善である。
ただし、写真のCameraとBatteryの型番は特定できていない。そのため今回の追加は
`master3x_demo_camera_head` と `generic_4s_850mah` というデモ用部品で、
実製品の仕様としては扱っていない。

## Master3X追試で分かった剛体再現上の課題

外観の違和感を再確認した結果、問題は細かなディテール不足だけではなく、
**剛体としての外形・部品境界・配置の推定精度**にある。

現在の`speedybee_master3x`は171 mmのwheelbaseから対称なTrue-X配置を導出しており、
`metadata.value_origin.motor_mount_positions_m`も
`derived_true_x_from_wheelbase`としている。wheelbaseは対角距離しか表さないため、
これだけでは前後方向・左右方向のMotor中心間隔やアーム角を一意に決められない。
実機寸法図、CAD、または各Motor中心座標が得られた場合は、True-X仮定より優先する。

現時点の公開一次資料からは、171 mm wheelbaseとは別にMotor中心の前後・左右間隔を
確定できる数値を確認できていない。したがって、別の長方形配置を推測で採用するのではなく、
True-X由来値は`derived`のまま保持し、追加の寸法図・実測・CADが得られた時点で更新する。

同様に`dimensions_m`はsimulation envelopeであり、frameの実外形寸法を直接表す
メーカー値ではない。Frameの受入時は、wheelbaseとは別に次を確認する。

- 前後方向・左右方向のMotor中心間隔。
- 中央プレートの前後長・左右幅・積層高さ。
- armの根元位置、長さ、幅、角度、厚さ。
- Head / Camera cageの構造寸法とFrameへの固定位置。
- Battery、AIO、VTX等を含む完成構成での占有体積。

### Frame / Head / Cameraの責務を分ける

現在の`master3x_demo_camera_head`はCamera本体に加えて、protective head、transmitter proxy、
two antennasを含む写真ベースのデモ部品である。この方法は完成外観を素早く作るには便利だが、
剛体モデルとしてはFrame側構造とCamera側部品の責務を曖昧にする。

今後は、資料から構造境界を確認したうえで原則として次のように分離する。

```text
Frame / Head
  - carbon plates / arms / standoffs
  - injection-molded or aluminum head structure
  - structural camera cage / support

Camera
  - camera body
  - lens / optical center
  - camera-side mount geometry

Electronics / Accessories
  - AIO / FC+ESC
  - VTX / Air Unit
  - receiver / GPS
  - antenna base and non-structural printed parts
```

HeadがFrameの商品variantとして販売・固定される場合はFrame構造として扱い、
Camera交換時にも残る部材をCamera Catalogへ焼き込まない。

### 内部部品は「見え方」と「物理」の両面から推定する

MuJoCo用途では基板の細かな電子部品まで再現する必要はないが、中央部が空洞に見える、
重心や慣性が不自然になる、といった差を避けるため、主要内部部品は簡略剛体として置く。

候補はAIO / FC+ESC、VTX / Air Unit、receiver、GPS、主要コネクタ・配線の塊である。
外形寸法、質量、搭載位置がメーカー資料から得られる場合は個別Catalog部品とし、
不明な場合はbox等のproxyとして推定値であることを明記する。

Frameの`geometry.visual`に内部電子部品を恒久的に焼き込むのではなく、将来的には
Assembly GraphでFrameとElectronicsを組み合わせる方を優先する。

## Master3Xの一次資料とcoverage

SpeedyBee公式の公開情報を再確認した結果、Master3Xの`3D Printing Files`は
フレーム全体のcarbon plate CADではなく、印刷用の小型アクセサリ／補助部品を中心とする。
そのため、公式STLであっても、**STLが表現していないFrame本体の形状根拠には使わない**。

Master3X本体の剛体再構成では、次の公式資料を主に使う。

- 製品ページ：variant、互換性、主要仕様、完成外観。
- Frame Downloadページ：公式配布資料の入口。現時点ではInstallation Instructionsが公開されている。
- Frame Installation：組立順、構造部品、搭載位置、ねじ・支柱、内部部品との境界。
- Frame Installation PDF：図版を含む一次資料。
- Master3X Frame Screws：上面／下面からの固定位置確認。
- Master 3X User Manual：完成機構成と搭載部品の確認。
- 3D Printing Files / Installation Guide：Head、camera support、antenna mount等の局所部品だけを補強する資料。

公式Frame Installationでは、少なくとも`Middle Plate`、`Top plate`、`Bottom Plate`、`Arm`、
`Arm Pad`、`Injection Molded Front Support`、`Injection Molded Side Plate`、
`Receiver Cover`、`Battery Anti-slip Pad`、`CNC Battery Strap Fixing Piece`、
`Multi-function GPS Mount`、`VTX Module`等が別部品として示されている。
またAIO、receiver、motor / motor wireはFrame同梱部品とは別扱いである。
この区分をCatalogのFrame / Electronics / Accessories境界の一次根拠にする。

Headについても、O3 Aluminum Alloy Head、O4 Pro Aluminum Alloy Head、Injection Molded Headが
別の組立手順として案内されている。したがってHeadをCamera本体へ焼き込まず、
Frame variantまたはFrameへ接続される構造部品として扱う方が自然である。

現時点では、carbon plateを含むMaster3X本体の完全なSTEP/DXF/CADが公式公開されている
ことは確認できていない。完全CADが見つからない限り、Frame本体は組立図・寸法・写真を
組み合わせてHakoniwa側のprimitive geometryへ落とす。

### 資料は「権威性」と「coverage」を分けて評価する

資料の強さは、メーカー公式かどうかだけでは決めない。まず、その資料が**対象部品のどこまでを
表現しているか**を確認する。同じメーカー公式STLでも、antenna mountだけを表すファイルから
arm長やcenter plate外形を推定してはいけない。

同じ部品・同じvariantを扱う場合の目安は次の通り。

```text
manufacturer CAD / STEP / DXF for the target rigid body
  > manufacturer dimension / assembly drawing for the target rigid body
  > manufacturer STL / mesh for the exact subpart it covers
  > manufacturer multi-view photographs
  > third-party measured CAD / STL
  > photo-based inference
```

異なるcoverageの資料同士は、この順序で単純比較しない。例えば「公式の小物STL」よりも、
Frame全体を示す公式組立図の方がFrame本体の剛体再現には有効である。

### STLは計測用証拠として扱い、Catalogへ抱え込まない

外部STLは最終成果物ではなく、必要な寸法を取り出すための証拠資料として扱う。
利用条件に問題がなければ、次の流れを基本とする。

```text
manufacturer STL
  -> bounds / dimensions / mount geometry / origin / axisを確認
  -> 必要な数値と由来をCatalog YAMLへ反映
  -> source URL、対象ファイル名、必要ならhashだけを記録
  -> STL本体はリポジトリへ同梱せず、計測後は保持しない
```

これにより、メーカーmeshへの実行時依存や再配布上の曖昧さを避け、
Catalog YAMLを正本としてGLB / MJCFを再生成できる。

## 情報の優先順位

「必須」は今回程度の外観を狙う際の収集・確認要件。資料が得られない場合は、
代わりに採用した仮定と再現できない範囲を明記する。

| 入力 | 優先度 | 必要な内容 | 不足すると精度を上げられない箇所 |
| --- | --- | --- | --- |
| 製品の識別 | 必須 | メーカー、型番、世代、サイズ・色・Head等のvariant | 別製品の寸法や写真を混ぜてしまう |
| 完成構成の一覧 | 必須 | 搭載部品、数量、含まれる付属品、Batteryの有無 | Camera、VTX、アンテナ等の欠落・二重計上 |
| 複数方向の静止画像 | 必須 | 上面・側面・前方斜め・後方斜め。下面も推奨 | 厚さ、前後差、隠れた部品、取付高さ |
| 絶対寸法の基準 | 必須 | 各部品の外形寸法。最低でも既知寸法を1つ | 画像から実寸への換算。1寸法だけでは各軸の精度は保証できない |
| 部品単体の画像 | 特徴部品で必須 | Frame、Motor、Propeller、Camera、Batteryの拡大画像 | 完成写真で隠れる輪郭・接合部・色分け |
| 接続面の情報 | 組立に必須 | mount位置、取付面、向き、consumer側の原点 | めり込み、浮き、向き違い、回転中心のずれ |
| 色・材質の参照 | 必須 | 黒い板、黄色い樹脂、金属、ガラスなどの区分 | シルエットは合っても製品らしく見えない |
| 寸法図・組立説明書 | 強く推奨 | 穴位置、板厚、支柱長、断面、部品番号 | 写真の遠近による誤差、隠れた寸法の推測 |
| CAD・3Dスキャン・mesh | さらに精度を上げる場合 | 単位・座標・部品分割とcoverageが分かるデータ | 複雑な曲面、正確な切り欠き、穴、細部 |
| Texture・材質資料 | 表面再現を上げる場合 | ラベル、ロゴ、繊維模様、透明度・粗さの参照 | 形状モデルだけでは再現しにくい表面の見た目 |

飛行中の画像は完成イメージとして役立つが、回転ブラーのあるPropellerは羽根形状の
根拠には使わない。透視画像の画素比を、そのまま寸法比として採用しない。
同じ部品を複数方向から比較し、寸法図または実測値を優先する。

## 部品ごとに必要な情報

| 部品 | 外観を作る入力 | 組立を成立させる入力 |
| --- | --- | --- |
| Frame | 上下・中央プレートの輪郭と厚さ、アーム形状、支柱、側板、フットの位置・色 | 前後・左右のMotor中心間距離、各mount面の高さ、Camera・Batteryの搭載領域 |
| Motor | ベル外径・高さ、底面、開口、上面、軸突出量 | 底面のボルトパターン、ねじ規格、取付面から軸・Propeller座面までの位置 |
| Propeller | 直径、枚数、羽根の平面形状・厚さ・ねじれ、ハブ径・厚さ、CW/CCW別の写真 | 中心穴、T-mount等の固定方式、固定穴間隔、Motor座面との関係 |
| Camera / Head | Camera型番、レンズ径・突出量、保護枠、放熱器、ケーブル・アンテナの構成 | Frame接続面、レンズ方向、チルト軸、取付幅とねじ、Headに含める部品 |
| Battery | セル数・容量・型番、外形、端子、ラベル、ベルトと配線 | 底面、搭載方向、配線出口、Frameの許容サイズ |
| アンテナ・付属品 | 外径・長さ、傾き、先端形状、部品番号 | 接続先、取付位置、完成品に含まれるか・選択部品か |

Frameのwheelbaseだけではアーム配置を一意に決められない。
今回のMotor配置はwheelbaseから対称Xを仮定している。実機の前後長と左右幅が
異なる場合は、各Motor中心の座標または前後・左右の距離が必要になる。
同様にMotorの「1507」はベル外形寸法の代わりにはならない。

## 原点・取付位置を決める要件

Catalogの長さはm、RPYはdegreeで保存する。UIのcm表示とは区別する。
部品の座標軸・原点・取付面の位置を決め、`assembly_ports`に記録する。
写真上の「だいたいこの辺」を使った場合は取付位置も推定値である。

接続後の姿勢は既存の規約に従う。

```text
T_child_world = T_parent_world × T_provider_port × T_adjustment × inverse(T_consumer_port)
```

例えばBatteryはconsumer portを底面に置き、Frame側の上面portと接続する。
Cameraのチルトを正確に見せるには、レンズ中心だけでなく取付軸の位置が必要になる。
穴径やボルトパターンが一致することと、周辺部品と干渉しないことは別に確認する。

現在のComposerにはPropellerをMotorの上に表示するboundsベースの補正がある。
見た目が接しているだけではport座標の正しさを証明できない。
寸法精度を上げる段階では、座面・ハブ厚・consumer原点を確認し、Python側の
配置とブラウザの表示補正を含めて比較する。

## 資料と推定値の残し方

製品URLだけでなく、参照した画像・説明書の箇所、対象variant、確認日をレビュー用の
記録に残す。チャット添付の写真も、どの特徴の根拠に使ったか記録する。
URL先で複数仕様が選択できる場合は、選択した仕様を必ず書く。

- `catalogs/sources/`：商用品のメーカーURL・説明書等の参照先。
- `catalogs/products/<category>/`：正規化した仕様・表示形状・port。
- `metadata.value_origin`：公開値、導出値、推定値を区別する。
- 専用docsまたはレビュー記録：画像の箇所、未確認寸法、採用した仮定、比較結果。

既存source schemaへ未定義フィールドを直接追加しない。確認日や画像番号などは
現時点ではレビュー記録に残す。今回の`visual_reference`のような記述だけでは、
第三者が元画像に戻れるとは限らないため、継続的な制作では参照先も管理する。

写真から推定したGeometryには、メーカー仕様と区別できる由来を付ける。
型番不明のCameraやBatteryはデモ部品として登録し、実製品が特定できた段階で
正しいCatalog項目を追加・選択する。画像内の見えない内部構造は断定しない。

## 実装と検証の要件

形状はCatalogを正本とし、GLBは生成物とする。ブラウザで製品ごとの形状を描き直さない。
`geometry.visual`、`geometry.collision`、`geometry.inertial`を分けて扱い、
見た目の細分化をそのまま質量・慣性の変更にしない。

今回の経路はbox・cylinder・capsule・sphere・ellipsoidの組合せで近似する。
それ以上の輪郭・曲面・表面再現が必要なら、mesh・textureの入力データと、
Catalog schema、Pythonの読込・GLB出力・MJCF出力の対応が必要になる。
CADファイルを入手しただけで、現在のCatalogが自動で読み込めるわけではない。

受入時は次を確認する。

- [ ] 製品variantと完成構成が参照写真に対応している。
- [ ] Frameの前後、胴体の縦横比、Motor間隔、Propeller枚数が参照に合う。
- [ ] 代表的な色分け・開口・部品配置が、通常のComposer表示サイズで見分けられる。
- [ ] 上面・側面・前後の斜め方向で、参照写真と生成モデルを比較した。
- [ ] Camera・Battery・Propellerが浮いたり不自然に貫通したりしていない。
- [ ] 部品の追加・交換・削除時に、別部品へ焼き込まれた残像や重複がない。
- [ ] 既知寸法を保持し、不明寸法の推定範囲を記録した。
- [ ] GLBを再生成し、実際のブラウザ表示を確認した。
- [ ] `doctor`、GLB/MJCF読込、必要な接続・姿勢テストが通る。

テスト成功は「生成物が読める／接続計算が成立する」の確認であり、外観の合格判定は
参照画像との比較で行う。寸法公差や画像誤差に数値目標が必要な案件では、基準寸法・
比較角度・許容誤差を制作前に決める。今回のデモに未測定の精度保証を付けない。

## Master3X次回作業チェックリスト

公式STLは小型のprinted/accessory partsだけを対象として使い、Frame全体の再構成は
Frame Installationと製品資料を中心に進める。

- [ ] Frame Installation PDFからTop / Middle / Bottom plate、arm、standoff、side plate、front supportの構造関係を整理する。
- [ ] Frame ScrewsのTop / Bottom Viewで固定位置と部品境界を確認する。
- [ ] wheelbase以外にMotor中心の前後・左右間隔を確定できる資料があるか再確認する。見つからなければ推測値へ置換しない。
- [ ] center plate / arm / headの外形と高さを、公式写真の上面・側面・斜め前から比較する。
- [ ] Head variantをFrame構造として分離し、`master3x_demo_camera_head`からFrame側部材を移せるか整理する。
- [ ] AIO / VTX / receiver / GPSについて、Frame InstallationとUser Manualから搭載位置とおおよその占有体積を整理する。
- [ ] printed STLがHead / camera support / antenna mount等の局所部品に有用なら、寸法だけ計測してYAMLへ反映し、STL本体は保持しない。
- [ ] 推定値を`manufacturer` / `derived` / `estimated`へ再分類する。
- [ ] 修正後にFrame単体GLBを生成し、上面・側面・斜め前から公式写真と比較する。
- [ ] 完成Assemblyを再生成し、Frame構造とCamera / Electronicsの責務が混ざっていないことを確認する。

## 次の製品追加で渡す情報のテンプレート

```text
製品名・型番・variant:
メーカー製品URL:
部品一覧／同梱範囲（数量・別売品）:
目標となる完成構成（Camera、Battery等の型番を含む）:
完成写真（上面／側面／前斜め／後斜め）:
部品単体の拡大写真:
寸法図・説明書（該当ページ）:
既知の外形寸法・取付寸法と単位:
部品の原点・前方向・取付面:
色・材質・目立つ特徴:
CAD／mesh／textureの有無と利用条件:
未確認事項・推定を許容する箇所:
外観の合格基準（比較写真・角度・必要なら許容誤差）:
```

まず製品識別・複数方向の写真・外形寸法・取付位置を揃える。
正確な切り欠きや曲面が次の課題になったら、寸法図・CAD・実測資料を追加する。
飛行性能も合わせる場合は、別途、質量・重心・慣性・推力特性等の根拠が必要であり、
外観資料だけからそれらの精度を上げることはできない。
