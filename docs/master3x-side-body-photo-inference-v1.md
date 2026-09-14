# Master3X Side-Body Photo Inference v1

## 目的

Master3X の黄色い Injection-molded Side Plate を、単一の薄い平板ではなく、公式製品写真に見える立体的な成形部品として近似するための rooted inference を記録する。

この文書はメーカー寸法を追加で発見したという意味ではない。`docs/master3x-dimension-evidence.md` で確定している 11 mm の内部 stack bay と、メーカー一次資料で確認できる Side Plate の存在を固定条件とし、未公表の外形だけを写真シルエットから推定する。

## Source

- `S1` SpeedyBee Master3X Frame product page
  - https://www.speedybee.com/speedybee-master3x-frame/
- `S4` Master 3X Frame Installation PDF
  - Injection-molded Side Plate L/R が Frame 構成部品として明示される。
- 2026-09-15 にレビューで参照した SpeedyBee 公式製品画像
  - parts overview
  - top / bottom view
  - dimension image
  - 21 mm body-height promotion image
  - front-oblique product image

## 写真から確認できる形状特徴

公式画像では黄色い Side Plate は一定厚みの平板には見えない。

- 下側が上側より外へ張り出し、中央胴体に量感を与えている。
- 上側はやや細く、上下断面が台形 / wedge に近い。
- 前後端は直角に切れず、中央部から Front Support / rear structure へ絞られる。
- 側面には斜めの rib / brace が見え、長い平板一枚の印象ではない。
- 公式画像の `Master 3X body height approx 21 mm` と、既存 Evidence Matrix の 11 mm internal stack bay は、この成形部品の Z 範囲を拘束する。

## Geometry inference

### 固定する根拠

- Middle Plate 上面から Top Plate 下面までの internal bay: 11 mm
- Side Plate は Frame 側の構造部品
- 左右対称

### 推定する外形

単一 `side_plate` box を、同じ 11 mm bay 内で 3 段の box に分ける。

| tier | X length | Y thickness | Z height | Evidence |
| --- | ---: | ---: | ---: | --- |
| lower | 68 mm | 6 mm | 4 mm | photo-inferred |
| middle | 62 mm | 5 mm | 3 mm | photo-inferred |
| upper | 54 mm | 4 mm | 4 mm | photo-inferred |

3 段の内側面は左右それぞれ `|Y| = 14 mm` に揃え、外側面だけが下ほど張り出す。これにより正面から見た断面を台形状に近づける。

Z 範囲は連続させる。

```text
middle plate top = 7.5 mm
lower  =  7.5 .. 11.5 mm
middle = 11.5 .. 14.5 mm
upper  = 14.5 .. 18.5 mm
top plate bottom = 18.5 mm
```

X 方向の前後端は、front / rear ramp box を pitch させて、写真に見える絞り込みを近似する。斜め brace は視認できる範囲だけ残す。

### 不確かさ

この tier 寸法はメーカー図面ではなくシルエット近似である。

- X length: おおむね ±4 mm 程度の不確かさ
- Y thickness: おおむね ±1.5 mm 程度の不確かさ
- ramp angle: 見た目近似でありメーカー角度ではない

CAD / 実測値が得られた場合は置換する。

## 今回変更しないもの

- Motor center X/Y
- Arm yaw / root / planform
- Plate planform L/W
- Front Support camera opening
- Interface Variant / Port
- mass / inertia
- Battery geometry

## Acceptance

- [ ] 正面・斜め前から、黄色い中央部が薄板ではなく立体的に見える。
- [ ] 下側が上側より外へ張り出す。
- [ ] X 方向も上側が短く、中央部が台形 / wedge の印象になる。
- [ ] 11 mm internal stack bay を越えない。
- [ ] 左右対称である。
- [ ] Motor / Arm / Interface の既存値を変更しない。
