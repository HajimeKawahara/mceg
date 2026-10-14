# 計算例：純H₂のフガシティから溶解H₂へ

**1700 K・7500 bar**では、溶解度則に記録された温度・総圧の区間に
入力条件が含まれます。一方、上流のEOSは、報告された純H₂のPVTデータ範囲の
外で評価されます。最終的な溶解H₂濃度の精度は**不明**です。
これが最初の具体的なMCEGの例です。正常終了する計算にも、外挿と証拠不足が
同時に含まれることが分かります。

## 計算と成果物

ExoGibbsの既存の
[`compare_solubility_laws.py`](https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/examples/comparisons/compare_solubility_laws.py)
からH₂の計算経路を取り出しました。純粋な分子状H₂を仮定し、気体モル分率を1、
根の選択を`vapor`とします。実際の溶融体組成は未指定です。ここでは溶解度則を
評価しており、気体・マグマ平衡、化学種分配、相安定性は解いていません。

1. ExoGibbsの純ガス用アダプターが7500 barを7.5e8 Paに換算し、ExoEOSの
   `ZhangDuanEOS.from_species(("H2",))`から1700 Kでの`ln(phi_H2)`を取得します。
2. 純ガスのフガシティを`f_H2_bar = exp(ln(phi_H2)) * 7500`で計算します。
3. ExoGibbsで`X_H2 = f_H2_bar * exp(-11.403 - 0.76 * 0.75)`を評価します。
   ここで0.75 GPaは**実際の溶融体圧力**であり、フガシティとは別の入力です。

`X_H2`は溶解H₂のモル分率です。温度はEOSに入力されますが、溶解度関数には
温度や溶融体組成の引数がありません。引数にないことは、経験則の温度・組成に
関する制約がないことを意味しません。

モデル契約は[純H₂ EOS](../../contracts/zhang_duan_h2.yaml)と
[H₂溶解度](../../contracts/h2_solubility.yaml)の2件です。
[`case.yaml`](../../examples/h2_solubility/case.yaml)には入力、接続方法、
**手作業で記述した**9件の判定を保存しました。これはこの例専用の形式であり、
新しい契約スキーマではありません。`mceg` CLIには渡さないでください。
[`run.py`](../../examples/h2_solubility/run.py)は固定条件で計算を再実行し、
[`result.json`](../../examples/h2_solubility/result.json)には数値結果、検査結果、
環境、上流revision、選択したソースのhashを記録します。
実行スクリプトは科学的な分類を計算・更新しません。

2026-10-15 JSTにCPU・float64で実行した結果は次のとおりです。

| 量 | 計算値 |
| --- | --- |
| H₂フガシティ係数`phi` | 2.256112 |
| H₂フガシティ | 16920.84 bar |
| 溶解H₂モル分率 | 0.106811 |
| 理想フガシティ`f = P`での比較値 | 0.0473427 |
| 非理想／理想の濃度比 | 2.256112 |

この比は、実際の溶融体圧力を固定したときに溶解度則がフガシティに比例することから
生じます。数値モデルの帰結であり、物理的な予測として検証された値ではありません。

## 適用条件の手動監査

| 対象 | 分類 | 根拠と限界 |
| --- | --- | --- |
| EOSの温度 | 外挿 | 1700 Kは、報告された純H₂のPVTデータ区間250–423 Kを超える。 |
| EOSの圧力 | 外挿 | 750 MPaは、報告された純H₂のPVTデータ区間2–700 MPaを超える。 |
| 溶解度の温度：メタデータ | 記録範囲内 | 1700 Kは1673–1773 Kに含まれる。 |
| 溶解度の温度：定式化文献 | 記録範囲内 | 1700 KはSeoのより狭い1673–1723 Kにも含まれる。 |
| 溶解度の総圧 | 記録範囲内 | 0.75 GPaは0.7–3 GPaに含まれる。原著要旨でも研究全体の同区間を確認。 |
| 溶解度のH₂フガシティ | 不明 | 実験で確認されたフガシティ範囲を確立できていない。 |
| 溶融体組成 | 不明 | Seoは玄武岩質珪酸塩を対象とするが、この例の実際の組成は未指定。 |
| 採用した溶解度の較正 | 不明 | 後年の較正が従来の濃度換算に疑義を示している。 |
| 接続した計算全体の精度 | 不明 | この条件での実験比較や不確かさの上限を確立できていない。 |

EOSの範囲の出典は[Zhang and Duan (2009), Table 5](https://doi.org/10.1016/j.gca.2009.01.021)
です。これはPVT比較データの範囲であり、EOSの根本的な限界や、実証された
フガシティ誤差の上限ではありません。温度・圧力を別々に示した上下限は、
その長方形全体での検証を意味しません。より広い混合物の範囲も、今回の純H₂の
精度を保証するものではありません。

溶解度の2種類の温度区間は、それぞれの出典とともに保持しました。
[上流のメタデータ](https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/src/exogibbs/solubility/volatile.py#L68-L88)
と[Seo et al. (2024), Section II.3・Eq. 6](https://arxiv.org/html/2408.17056v1#S2.SS3)
の違いは今回の温度判定を変えませんが、黙って統合すべきではありません。
どちらかの区間に入るだけでは、溶解度計算全体を物理的に適用可能と分類できません。

実験条件について、Seoは二次資料です。この文章は確認しましたが、玄武岩系列の
元の実験表との照合は未完了です。[出典追跡](provenance.md)に、その未照合を
明示しました。`within_reported_range`は原実験による検証済みを意味しません。

[一次資料監査](h2_primary_audit.md)では、研究全体の圧力範囲と、玄武岩・安山岩が
別系列だったことを原著要旨から直接確認しました。メタデータの温度上限の違いと、
実装とSeoの式の一致も記録し、元の経験式のフィットは未確認として残しました。
後年の図の説明から温度上限の違いが対象物質による可能性は見えましたが、これは
まだ二次資料の情報です。更新したのは証拠の経路であり、9件の分類と計算値は変わりません。

[Chaudhari et al. (2025)](https://doi.org/10.1007/s00410-025-02272-y)は従来の
赤外分光による濃度較正を見直しています。この知見から今回の値に一律の補正を
定めることはできないため、結果を**10で割る補正はしていません**。

## 数値検証

5件のモデル契約はすべてコアValidatorを通過しました。MCEGのテストでは、
手動記録の参照先、出典追跡、実行記録の整合性を検査しています。
これらのテストに上流パッケージやJAXは不要です。

上流テストの実行環境はPython 3.12.7、JAX 0.6.2、NumPy 2.1.0、
pytest 8.3.3、CPU、x64です。ExoEOSの公開パラメーター生成テストは
**1件成功**しました。ExoGibbsのスカラー則の参照値テスト、配列入力テスト、
比較例のフガシティ単位・溶融体圧力テストは合計**8件成功**しました。
これらが検査するのは定数、式、接続の規約であり、最終濃度の実験的な妥当性ではありません。

監査対象の上流checkoutを兄弟ディレクトリに置き、依存関係を導入した環境で、
MCEGのルートから次のように実行できます。

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=src:../exoeos/src:../exogibbs/src:../exogibbs
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1
python -m pytest -q -p no:cacheprovider ../exoeos/tests/unittests/zhang_duan_test.py::test_published_species_factory_inserts_table_parameters
python -m pytest -q -p no:cacheprovider ../exogibbs/tests/unittests/solubility/meltyq_test.py::test_meltyq_laws_match_independent_reference_values ../exogibbs/tests/unittests/solubility/meltyq_test.py::test_laws_broadcast_array_inputs ../exogibbs/tests/unittests/examples/solubility_comparison_test.py::test_exoeos_fugacity_units_and_actual_melt_pressure
python examples/h2_solubility/run.py --output /tmp/h2-solubility-result.json
```

実行スクリプトの4件の検査は成功しました。アダプターとEOS直接呼び出しの一致、
EOS圧力の往復計算、実際の溶融体圧力を使った2種類の溶解度式を確認しています。同じ実圧力で理想気体の
フガシティを仮定した比較値も計算します。これらは上流実装を共有する数値検査であり、
独立した物理的証拠ではありません。ExoEOS・ExoGibbsはこの例を実行する場合だけ
必要で、MCEG本体の依存関係には追加していません。出典追跡はコアスキーマへの任意の追加です。

## 次に調べるべきこと

1. 溶解度式の実験で用いたH₂フガシティ・組成・酸化還元条件の範囲を調べ、
   出典による温度上限の違いを整理する。
2. 現在の濃度較正と、対象のH₂条件で根拠のあるEOSを検討し、フガシティ・
   溶解濃度の不確かさを評価する。
3. 実際の溶融体を指定し、接続した計算全体を測定値と比較する。
4. 必要となった情報から、出典と単位を持つ条件表現・明示的な接続を設計する。
   汎用評価器や単一の適用可能性スコアの導入はまだ行わない。

残されたスキーマの課題は[設計上の問題点](design_questions.md)に整理しています。
