"""Optional Japanese UI text; scientific records and machine reports stay original."""

import re
from string import Formatter
import textwrap
import unicodedata


# Only application-owned messages are translated. Unknown/free-form text is retained.
JA = {
    "MCEG checks: recorded structure, source audits and scoped evidence reuse": "MCEG確認：記録の構造、出典の確認、条件を指定した証拠の再利用",
    "Structure": "構造",
    "Source audit": "出典の確認",
    "Selected files": "対象ファイル",
    "Temperature range": "温度範囲",
    "Sample coverage": "試験点の対応",
    "Evidence reuse": "証拠の再利用",
    "Physical validation": "物理的妥当性",
    "Curated context": "curated gasの指定条件",
    "archived example defaults with CLI overrides": "保存済み例の既定値とコマンドで指定した値",
    "Invalid contract": "契約の形式に問題があります",
    "Cannot read the reviewed evidence": "レビュー済みの証拠を読み込めません",
    "Use the provider-owned mceg/contracts/curated_gas.yaml": "提供元のmceg/contracts/curated_gas.yamlを指定してください",
    "Requested T/P/network is an archived sample": "指定した温度・圧力・反応ネットワークに一致する試験点が記録されています",
    "No archived sample established for the requested T/P/network": "指定した温度・圧力・反応ネットワークに対応する試験点を確認できません",
    "Recorded files changed or are missing": "記録されたファイルに変更または欠落があります",
    "The recorded numerical comparison is incomplete": "記録された数値比較が未完了です",
    "Requested condition is not covered by an archived sample": "指定した条件は記録済みの試験点に含まれていません",
    "Temperature is outside the numerical evaluation interval": "温度が数値評価の範囲外です",
    "Reviewed evidence supports this context": "レビュー済みの証拠が指定した条件での主張を支持しています",
    "Support is limited to the explicitly reviewed equilibrium_verification claim.": "支持の対象は、明示的にレビューしたequilibrium_verificationの主張に限られます。",
    "Whole-mixture physical accuracy is unestablished": "混合物全体の物理的な精度は確認されていません",
    "No automatic evidence-reuse rule for this model": "このモデルには証拠の再利用を自動判定する規則がありません",
    "Stored support assessments are scoped records; inspect a specific assessment with mceg explain": "支持の評価は対象と条件ごとの記録です。mceg explainで個別の評価を確認してください",
    "Recorded classification differs from the current Condition/Context; review the changed record.": "記録された判定が現在のCondition/Contextと一致しません。変更された記録を確認してください。",
    "  Context describes the requested target; the installed numerical environment is not inspected.": "  これは評価対象として指定された条件です。インストール済みの計算環境は調査していません。",
    "  Recorded v0.1 declarations (not reassessed by structure/source checks):": "  記録済みのv0.1宣言（構造・出典の確認では再評価しません）：",
    "  Recorded v0.2 assessments (each bound to its own subject and context):": "  記録済みのv0.2評価（それぞれ固有の対象と条件に対応）：",
    "UNKNOWN identifies missing support or review gaps. These checks do not run numerical solvers.": "UNKNOWNは証拠や確認が不足している箇所を示します。この確認では数値ソルバーを実行しません。",
    "Next steps": "次の作業",
    "passed": "件 PASS",
    "failed": "件 FAIL",
    "unknown": "件 UNKNOWN",
    "No contracts selected. Use a contract file or a directory containing YAML contracts.": "契約が選択されていません。契約ファイルまたはYAML契約を含むディレクトリを指定してください。",
    "No contracts selected.": "契約が選択されていません。",
    "MCEG next steps: recorded gaps and suggested work; no evidence is changed.": "MCEGの次の作業：記録された未確認事項と作業案を表示します。証拠は変更しません。",
    "Contract text, authored instructions and IDs are shown in their original language.": "契約の本文、記録された作業指示、IDは原文のまま表示します。",
    "Requested curated context (not an inspection of the installed environment):": "curated gasの指定条件（インストール済み環境の調査結果ではありません）：",
    "Use --json to inspect all joint samples.": "すべての試験点の組み合わせを見るには--jsonを指定してください。",
    "Recorded next step": "記録された次の作業（原文）",
    "Suggested next step": "提案する次の作業",
    "Comparison target": "比較対象",
    "Comparison note": "比較についての記録",
    "Review progress": "確認作業の進み具合",
    "Follow-up work has a completion record. Its results are listed below.": "この記録に関する作業には完了報告があります。その結果を下に示します。",
    "The sources below have follow-up comparison results. Their old 'not_checked' entries are kept as history.": "下の資料は、その後の比較結果が記録されています。「未比較」は当時の記録として残しています。",
    "The compared parts agree.": "比較済み：確認した範囲では一致しています。",
    "Compared; differences remain to be explained.": "比較済み：違いが見つかり、その理由や扱いの確認が残っています。",
    "The source-reading task has a completion record. The old inspection state is kept as history.": "資料を読んで確認する作業には完了報告があります。元の確認状況は当時の記録として残しています。",
    "Task completion does not establish model accuracy. Use the linked assessments to see what the evidence supports.": "作業の完了だけでは、モデルの精度は保証されません。確認できた精度や条件は、下に案内する評価で確認してください。",
    "Original record (history retained)": "元の記録（当時の状態を保持）",
    "Completed follow-up": "完了した作業（記録）",
    "Recorded task completion only; historical source fields and support judgments are unchanged.": "これは作業の完了報告です。以前の出典確認や精度の評価は、当時の記録として残しています。",
    "Needed": "必要なもの",
    "Source": "出典",
    "Completion": "完了条件",
    "Inspect": "詳しく確認",
    "Evidence gaps (IDs for --evidence)": "証拠の未確認事項（--evidenceで指定するID）",
    "Unknown Claim IDs": "評価がunknownの主張ID",
    "Evidence": "証拠（Evidence）",
    "Claim": "科学的主張（Claim）",
    "Assessment": "評価（Assessment）",
    "Condition": "比較する条件（Condition）",
    "Id": "ID",
    "Kind": "種類",
    "Revision": "版",
    "Summary": "概要",
    "Statement": "主張の内容",
    "Scope": "対象範囲",
    "Sources": "出典",
    "Provenance": "出典の追跡情報",
    "Role": "資料の役割",
    "Location": "該当箇所",
    "Inspection": "確認状況",
    "Note": "記録された補足",
    "Derived from": "元になった証拠",
    "Comparison": "比較結果",
    "Result": "記録された結果",
    "Status": "記録された状態",
    "Origin": "評価の由来",
    "Method": "評価方法",
    "Description": "説明",
    "Subject": "評価対象（Subject）",
    "Context": "計算条件（Context）",
    "Claim revision": "主張の版",
    "Condition revision": "比較する条件の版",
    "Reasons": "理由",
    "Implementation": "実装",
    "Repository": "リポジトリ",
    "Entry points": "実装の入口",
    "Quantities": "物理量",
    "Settings": "設定",
    "Artifacts": "保存された成果物",
    "Samples": "記録された試験点",
    "Value": "値",
    "Unit": "単位",
    "Quantity": "物理量",
    "Interval": "区間",
    "Lower": "下限",
    "Upper": "上限",
    "Closure": "端点の扱い",
    "Coverage": "確認した範囲",
    "Classification": "条件との比較結果",
    "Missing file": "欠落したファイル",
    "Use --plain for the original text layout or --json for complete records.": "従来のテキスト表示は--plain、完全な記録は--jsonで確認できます。",
    "subject": "評価対象（Subject）",
    "context": "計算条件（Context）",
    "claim": "科学的主張（Claim）",
    "condition": "比較する条件（Condition）",
    "missing_provenance": "出典の追跡情報がありません",
    "source_not_fully_inspected": "出典の必要な内容を確認できていません",
    "unknown_source_role": "一次資料か二次資料か未確認です",
    "primary_source_not_identified": "一次資料が特定されていません",
    "comparison_not_checked": "この記録では、元の資料との比較結果がまだ記録されていません",
    "comparison_discrepancy": "比較した結果、元の資料と異なる点が記録されています",
    "An explicitly recorded joint sample matches; other context fields are not evaluated.": "明示的に記録された条件の組み合わせに一致します。他の条件項目は評価していません。",
    "No recorded joint sample matches; interpolation and physical accuracy are not assessed.": "一致する条件の組み合わせは記録されていません。補間と物理的精度は評価していません。",
    "Review the listed source for this precise scope and record its role, location and inspection state.": "この範囲に関係する出典を確認し、資料の役割、該当箇所、確認状況を記録してください。",
    "Add the inspected passage or code location and any upstream evidence/comparison; a source locator alone is insufficient.": "確認した文章やコードの位置と、元の証拠・比較結果を記録してください。出典の場所を示すだけでは確認完了になりません。",
    "Obtain and inspect the relevant full text or data. If access is restricted, a human may need an institutional library or an authorized author copy.": "必要な本文やデータを入手して内容を確認してください。閲覧制限がある場合は、人間が所属機関の図書館や著者から正規の提供を受ける必要があるかもしれません。",
    "Record the exact equation/table/page, relevant values, units and material scope; mark only the content actually inspected.": "該当する式・表・ページ、値、単位、対象物質の範囲を記録し、実際に確認した内容だけを確認済みとしてください。",
    "The listed source content, not only its abstract or citation.": "出典の本文やデータ。要旨や引用情報だけでは足りません。",
    "Determine whether this is an original source or a later account, and identify the original work.": "一次資料か後の解説かを確認し、元の研究を特定してください。",
    "Record the verified source role and link the inspected original evidence.": "確認した資料の役割を記録し、内容を確認した一次資料の証拠へリンクしてください。",
    "Trace the scoped statement to its original theoretical, experimental or observational source.": "対象の記述を元の理論・実験・観測資料までたどってください。",
    "Add a primary evidence record and the inspected derivation/comparison links.": "一次資料の証拠記録と、確認した導出・比較のリンクを追加してください。",
    "Compare the equations, tables or code at the source locations below. Check values, units, definitions and the materials and conditions covered.": "下に示す資料の式・表・コードと、対象の実装や記述を見比べてください。値だけでなく、単位や定義、扱う物質・条件も確認してください。",
    "After inspecting both sources, record where you compared them, what agrees and what differs.": "両方の資料を確認してから、見比べたページ・式・表と、一致した点・異なる点を記録してください。",
    "The comparison found differences. Check whether units, definitions, conditions or transcription explain them before changing a claim.": "比較は済んでいますが、違いが見つかっています。単位・定義・対象条件や転記の誤りで説明できるかを確認してください。",
    "Record how each difference was explained, or which differences still need investigation.": "違いの理由が分かった点と、まだ調べる必要がある点を記録してください。",
    "Define the physical observable, accuracy criterion and calculation conditions, then obtain relevant independent measurements or observations.": "何をどの条件で、どれくらいの誤差まで再現したいかを決め、その条件に合う実験・観測データを用意してください。",
    "Record the comparison as new physical Evidence and a scoped Assessment; numerical solver agreement alone does not establish physical accuracy.": "実験・観測との比較結果と、確認できた精度・条件を新しいEvidenceとAssessmentに記録してください。計算同士の一致だけでは、実験に合うかは分かりません。",
    "Review the claim's scope and evidence for the intended implementation and conditions.": "使用する実装と条件に対して、主張の範囲と証拠を確認してください。",
    "Record a separate scoped support Assessment; preserve the earlier declaration and execution results.": "対象を明示した支持のAssessmentを別に記録し、以前の宣言と実行結果を保持してください。",
    "Review the imported declaration before using it for a new context.": "取り込んだ宣言を新しい条件で使う前に、その適用範囲を確認してください。",
    "Keep the imported Assessment attached to its original Claim revision; add a separate reviewed Assessment for the new target.": "取り込んだAssessmentは元のClaimの版に対応させたまま、新しい対象への評価を別にレビューして追加してください。",
    "Create a new context and run mceg assess with a new output file; preserve this assessment.": "新しいContextと出力ファイルを指定してmceg assessを実行し、この評価も保持してください。",
    "Run the provider verification for the requested conditions and environment, retaining a new execution receipt and outputs.": "指定した条件と環境で提供元の数値検証を実行し、新しい実行記録と出力を保存してください。",
    "Review the new run's coverage and Claim criteria before adding its support Assessment.": "新しい実行が確認した範囲とClaimの判定基準をレビューしてから、支持のAssessmentを追加してください。",
    "Supply the missing quantities or settings identified in the reasons, using a new Context ID.": "理由に示された不足する量や設定を、新しいContext IDで指定してください。",
    "Run mceg assess with the new context and a new output file; retain the old assessment.": "新しい条件と出力ファイルでmceg assessを実行し、以前の評価も保持してください。",
    "Obtain numerical evidence at the requested joint conditions, or review an explicit interpolation method.": "指定した条件の組み合わせで数値的な証拠を取得するか、明示的な補間方法をレビューしてください。",
    "Record actual new samples and their evidence; range inclusion alone is insufficient.": "実際に確認した新しい試験点と証拠を記録してください。範囲内にあるだけでは十分ではありません。",
    "Review whether the intended calculation requires evidence beyond this source's reported interval.": "計算の目的に対して、この出典の報告範囲を超える証拠が必要か確認してください。",
    "Use an evidenced condition or obtain new scoped evidence; do not widen an interval merely to clear this result.": "証拠のある条件を使うか、新しい範囲の証拠を取得してください。この結果を解消するためだけに範囲を広げないでください。",
    "Correct the field or local reference identified in the validation error.": "形式の検証エラーで示された項目や参照先を修正してください。",
    "Run mceg check again; valid structure permits inspection but does not establish scientific support.": "mceg checkを再実行してください。構造が正しくても、科学的な支持が確立したわけではありません。",
    "Select an evidence ID below to see the source, recorded access/inspection notes and upstream comparisons.": "下の証拠IDを指定すると、出典、入手・確認状況の記録、元の資料との比較を見られます。",
    "Complete the scoped inspection and comparisons; obtaining a document alone does not complete the audit.": "必要な範囲の内容確認と比較を完了してください。文献を入手しただけでは確認完了になりません。",
    "Inspect the changed or missing paths listed below.": "下に示された変更・欠落したファイルを確認してください。",
    "Restore the archived files for a replay, or produce and review new evidence for the changed implementation; do not replace hashes to manufacture a pass.": "再現確認には保存時のファイルを復元するか、変更した実装の証拠を新たに作成・レビューしてください。ハッシュの書き換えだけでPASSにしないでください。",
    "Review the requested temperature, pressure and network against the archived scope.": "指定した温度・圧力・反応ネットワークを、記録された検証範囲と照合してください。",
    "For a new condition, obtain actual new numerical evidence and a scoped review; no interpolation support is inferred.": "新しい条件では、実際の数値検証の証拠とその範囲のレビューが必要です。補間の妥当性は自動推定しません。",
    "Use --context with the actual intended quantities, composition, environment and tolerance.": "実際に使用する量、組成、環境、許容誤差を--contextで指定してください。",
    "A provider environment and the relevant numerical comparator; mceg explain does not execute them.": "提供元の計算環境と対応する比較用の数値計算。mceg explain自体はこれらを実行しません。",
    "Inspect the recorded Claim/Assessment scope and any changed contract or receipt.": "記録されたClaim/Assessmentの範囲と、契約や実行記録の変更を確認してください。",
    "Define or review a scoped reuse policy with evidence for the intended target; imported support is not a new evaluation.": "使用する対象への証拠に基づき、再利用できる範囲と規則を定めるかレビューしてください。取り込んだ支持の宣言は新しい評価ではありません。",
    "Inspect the recorded assessment and its context using --assessment ID.": "--assessment IDで記録された評価とその条件を確認してください。",
    "Address the stated reason and append a separately identified assessment; preserve the old record.": "示された理由に対応し、別のIDの評価を追加してください。以前の記録も保持してください。",
}

# Match complete application messages, preserving interpolated IDs, paths and values.
TEMPLATES = {
    "Collected {count} contracts; selected {selected}": "{count}件の契約を検出、{selected}件を選択",
    "v{version} structure and local references are consistent": "v{version}の構造と内部の参照先は整合しています",
    "{count} recorded input/output hashes match": "記録された入出力ハッシュの{count}件が一致しています",
    "{count} evidence records have complete declared source traces": "証拠の{count}件で、記録上の出典確認が完了しています",
    "{temperature} K; within numerical interval {bounds} K": "{temperature} Kは数値評価の範囲{bounds} Kの内側です",
    "{temperature} K; outside numerical interval {bounds} K": "{temperature} Kは数値評価の範囲{bounds} Kの外側です",
    "Missing temperature K; not compared with numerical interval {bounds} K": "温度が未指定です。数値評価の範囲{bounds} Kとの比較はできません",
    "Missing context: {fields}": "不足する条件項目：{fields}",
    "Different context: {fields}": "記録と異なる条件項目：{fields}",
    "Historical numerical result: {result}": "過去の数値検証結果：{result}",
    "Assessment: {id}": "評価ID：{id}",
    "Missing quantity: {name}": "不足する量：{name}",
    "Missing sample coordinates: {names}": "試験点との比較に必要な条件が不足しています：{names}",
    "{value} compared with closed interval {bounds}; marginal coverage only.": "{value}を両端を含む範囲{bounds}と比較しました。個々の量についての範囲だけを確認しています。",
    "{value} compared with closed interval {bounds}; numerical_evaluation coverage only.": "{value}を両端を含む範囲{bounds}と比較しました。数値評価の範囲だけを確認しています。",
    "context={context}; within_reported_range": "条件={context}；報告された範囲内",
    "context={context}; outside_reported_range": "条件={context}；報告された範囲外",
    "context={context}; at_recorded_sample": "条件={context}；記録された試験点に一致",
    "context={context}; not_sampled": "条件={context}；記録された試験点に一致しない",
    "context={context}; unknown": "条件={context}；必要な情報が不足",
    "Supply context fields: {fields}": "不足する条件項目を指定してください：{fields}",
    "Supply the actual context fields: {fields}": "実際に使用する条件を指定してください：{fields}",
    "{passed} passed, {failed} failed, {unknown} unknown": "PASS {passed}件、FAIL {failed}件、UNKNOWN {unknown}件",
}


def _pattern(template):
    return re.compile("".join(re.escape(literal) + (f"(?P<{field}>.*?)" if field else "")
                              for literal, field, _, _ in Formatter().parse(template)))


PATTERNS = [(_pattern(source), target) for source, target in TEMPLATES.items()]


def translate(message, lang):
    if lang != "ja":
        return message
    if message in JA:
        return JA[message]
    for pattern, target in PATTERNS:
        match = pattern.fullmatch(message)
        if match:
            return target.format_map(match.groupdict())
    return message


def check_message(check, lang):
    message = check["message"]
    if message in JA:
        return translate(message, lang)
    if check["name"] == "evidence_reuse" and lang == "ja":
        return "；".join(translate(part, lang) for part in message.split("; "))
    return translate(message, lang)


def detail(message, lang):
    prefix, separator, issue = message.rpartition(": ")
    if separator and issue in {"missing_provenance", "source_not_fully_inspected", "unknown_source_role",
                               "primary_source_not_identified", "comparison_not_checked", "comparison_discrepancy"}:
        return prefix + separator + translate(issue, lang)
    return translate(message, lang)


def language_command(command, lang):
    return command + " --lang ja" if lang == "ja" else command


def add_language_argument(parser):
    parser.add_argument("--lang", choices=("en", "ja"), default="en",
                        help="Language for human-facing output (default: en); JSON and stored text remain original")


def wrap(text, width, indent, lang):
    if lang != "ja":
        return textwrap.fill(text, width=width, subsequent_indent=indent)
    # Count terminal cells so Japanese prose fits without adding a dependency.
    def cell_width(char):
        return 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1

    lines, line, cells = [], "", 0
    for token in re.findall(r"[!-~]+|.", text, re.DOTALL):
        size = sum(cell_width(char) for char in token)
        if cells + size > width and size <= width - len(indent):
            lines.append(line.rstrip())
            line, cells = indent, len(indent)
        for char in token:
            size = cell_width(char)
            if char == "\n" or cells + size > width:
                lines.append(line.rstrip())
                line, cells = indent, len(indent)
                if char.isspace():
                    continue
            line += char
            cells += size
    return "\n".join([*lines, line.rstrip()])
