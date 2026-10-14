# 証拠を一次資料までたどる

MCEGは、記録された引用関係を一次資料までたどり、未確認の資料や未照合の箇所を
表示できます。転記された数値や適用条件について、どこを調べる必要があるかを
明確にする機能です。論文の読解・引用元の自動発見・数値の自動比較や、一次資料
そのものの正しさの判定は行いません。

## 情報ごとに確認範囲を定める

証拠は、確認できる一つの数値や条件を単位にし、量・単位・物質・条件を
`summary`と`scope`に記録します。出典や確認状況が違う情報は分けます。
同じ論文でも、自身の計算については一次資料、利用した実験データについては
二次資料になり得ます。役割は論文全体ではなく、その証拠の対象について指定します。

任意の`provenance`フィールドに次の情報を追加しました。

| フィールド | 意味 |
| --- | --- |
| `role` | 対象についての`primary`、`secondary`、`implementation`、`unknown` |
| `location` | ページ・表・行・式・文章・コード位置。不明なら、その旨を記録 |
| `inspection` | 対象部分の確認状況：`not_inspected`、`partial`、`inspected` |
| `note` | 何を確認し、何が不足しているか |
| `derived_from` | 同一契約内の引用元。各リンクに`evidence`、`comparison`、`note`を記録。省略時は空 |

リンクの`comparison`は、`not_checked`、`consistent`、`discrepancy`です。
これらは手作業で記録する照合結果です。`consistent`には、関係する数値・単位・
対象範囲・変換の対応を説明します。数値が同じでも、適用対象を引き継げるとは
限りません。`discrepancy`は観察した不一致を残し、どちらが誤りかまでは断定
しません。意図した近似で違いが生じた場合も、理由を記録します。

Validatorは、`consistent`または`discrepancy`を記録する場合、両側の資料が
対象について`inspection: inspected`であることを要求します。参照切れ・重複・
循環参照を拒否します。未確認や不一致そのものは、保存すべき監査情報として扱います。

## H₂の例

[H₂の契約](../../contracts/h2_solubility.yaml)に、次の証拠を分けて記録しました。

1. `formulation_temperature`：二次資料である
   [Seo et al. (2024)のEq. 6直前](https://arxiv.org/html/2408.17056v1#S2.SS3)
   に記載された温度範囲。この記述は直接確認済みです。
2. `experimental_temperature`：特定された元の実験論文
   [Hirschmann et al. (2012)](https://doi.org/10.1016/j.epsl.2012.06.031)。
   玄武岩系列の実験条件表は、この情報について未確認です。
   [著者所属機関に掲載された要旨](https://experts.umn.edu/en/publications/solubility-of-molecular-hydrogen-in-silicate-melts-and-consequenc/)
   から実験系列は確認できますが、それで該当する実験表を確認したことにはなりません。

両者のリンクは`not_checked`です。元の表を確認したかのような数値は追加して
いません。この経路だけでは式の数値係数の由来や、1723 Kと1773 Kの出典間の
違いについても決着しません。

```bash
python -m mceg --trace formulation_temperature contracts/h2_solubility.yaml
```

JSON出力には、二つの証拠と出典中の場所、引用関係と説明、次の未完了項目が現れます。

- `comparison_not_checked`：引用された範囲と原典の実験条件を照合していない。
- `source_not_fully_inspected`：一次資料の該当箇所が未確認。

`primary_sources`には`experimental_temperature`が現れますが、
`recorded_audit_complete`は**false**です。一次資料の引用先に到達することと、
内容を照合することを区別しています。ケースの`within_reported_range`も、
Seoに記載された区間内という意味を保ち、原実験による検証済みにはなりません。

その後の[一次資料監査](h2_primary_audit.md)で、実際の照合例も追加しました。

| 追跡対象 | 記録した結果 |
| --- | --- |
| `metadata_pressure` | 原著要旨の研究全体の圧力範囲と`consistent`。この限定された事実について照合完了。 |
| `metadata_temperature` | Seoの温度上限と`discrepancy`。さらに元の表は未照合であり、誤植とは断定しない。 |
| `implementation` | Seoの式・単位と`consistent`、元の経験式のフィットとは`not_checked`。 |
| `historical_calibration` | 確認済みの二次資料の記述から、本文未確認・役割不明の古い校正資料へつながる。 |

`infrared_recalibration`には、2025年の研究自身の測定という一次証拠を別に
記録しました。この証拠や圧力の照合完了によって、物理的精度の主張は変更しません。
同じ論文が、新しい測定については一次資料、過去の測定の説明については二次資料に
なることも、この例で示しています。

## 出力の意味と限界

記録されたすべての分岐をたどります。出典情報の欠落、役割不明、一次資料に
達しない経路、確認不足、未照合、不一致があれば、`recorded_audit_complete`は
trueになりません。共通の引用元は同じIDなら一度だけ表示します。別のIDが同じ
データを指すかは自動判定せず、独立した証拠の数や信頼度スコアも算出しません。

trueは、入力された記録が、全経路について一次資料まで確認・整合していると
宣言していることだけを意味します。宣言の真偽、依存する情報を漏れなく記録したか、
物理的な主張を支持するかは判定できません。主張や適用条件の状態は自動変更しません。

`--trace`は有効な入力ファイルごとに一つのJSONオブジェクトを出力します。
終了コード0は出力できたことを示し、監査に不足があっても0です。不正な入力や
存在しない証拠IDは1です。Pythonでは`trace_provenance(contract, evidence_id)`を
利用できます。従来の契約はそのまま読み込め、出典情報がない場合は
`missing_provenance`を表示します。

次の人手による作業は、元の表を入手し、対象物質と実験系列を選び、単位と条件を
照合して、その範囲について結果を記録することです。全文の自動取得、抽出、
単位を理解した比較、訂正履歴、契約をまたぐ出典の同一性は、この最小実装の対象外です。
