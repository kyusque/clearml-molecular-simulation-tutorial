# clearml_gamess

[English version](README.md)

`clearml_gamess/`は、GAMESSの計算をClearML Task/Pipelineで実行・追跡するための再利用コードをまとめたディレクトリです。

| ファイル | 役割 |
| --- | --- |
| `run_gamess.py` | GAMESSジョブを投入し、実行マニフェストJSONを書き出す |
| `track_gamess.py` | GAMESSログを追跡・判定し、抗出値を`tracking_metrics`に書き出す |
| `cml_task_run_gamess.py` | Pipelineの`run_gamess`ステップのTask定義（Agent上で実行） |
| `cml_task_track_gamess.py` | Pipelineの`track_gamess`ステップのTask定義（Agent上で実行） |
| `cml_pipeline_gamess.py` | `run_gamess`と`track_gamess`の2ステップを持つPipeline定義 |
| `examples/` | `.inp`と対応する`.cml.py`の投入例 |

## GAMESSのインストール

このリポジトリにはGAMESS本体は含まれていません。ClearML Agentが動くマシンにGAMESSをインストールしてください。

**Windows（推奨構成）**

`C:/Users/Public/gamess-64`に展開し、`rungms.bat`と`gamess.<version>.exe`がその中にある状態にします。`cml_task_run_gamess.py`はこのパスを既定で使います。

別の場所にインストールした場合は、Agentを起動する環境に`CLEARML_GAMESS_DIR`を設定してください。`tools/start_clearml_agent.py`でAgentを起動する場合は、`rungms.bat`を自動で探してAgentに渡します。

**macOS/Linux**

GAMESSをソースビルドして`rungms`が使える状態にしてください。`tools/start_clearml_agent.py`でAgentを起動する場合、`rungms`が`PATH`にあれば起動時に自動検出して`CLEARML_GAMESS_DIR`としてAgentに渡します。`PATH`にない場合は`CLEARML_GAMESS_DIR`を手動で設定してください。

## .cml.py の役割

`.cml.py`はユーザーが編集するClearMLタスク投入用スクリプトです。プロジェクト名・キュー・GAMESS入力ファイル・CPU数などの実行条件だけを書きます。

ログ・実行マニフェスト・metricsなどの生成物のパスはユーザーが直接書きません。Agentが実行するTask（`cml_task_run_gamess.py`・`cml_task_track_gamess.py`）が計算ごとに一時ディレクトリを作って管理します。

## 生成されるアーティファクト

| アーティファクト名 | 何か |
| --- | --- |
| `gamess_input` | Agentが実際GAMESSへ渡した入力ファイル |
| `gamess_run_manifest` | track側への引渡しJSON（ログパス・実行環境など） |
| `gamess_rungms` | 実際に起動した`rungms`または`rungms.bat` |
| `gamess_log` | GAMESSの出力ログ（テキストプレビュー付き） |
| `tracking_metrics` | 終了判定結果（`gamess_status`・`return_code`など） |
| `gamess_temp` | scratch/restartファイル（有効にした場合のみ） |

Pipeline Task上では`run_gamess_`・`track_gamess_`プレフィックスで集約されます。

## 終了判定

GAMESSログ中の次のメッセージで終了状態を判定します。

- `EXECUTION OF GAMESS TERMINATED NORMALLY` → `gamess_status: completed`
- `EXECUTION OF GAMESS TERMINATED -ABNORMALLY-` → `gamess_status: failed`

どちらも現れなければ`running`または`unknown`になります。GAMESSが失敗していた場合は、アーティファクトを残したうえでtrack側のTaskをfailedにします。

## Task名の規則

ClearML UIでは長い名前が省略されるため、入力ファイル名（拡張子なし）を先頭に置きます。

```
water_rhf_sto3g_opt.cml_pipeline_gamess
water_rhf_sto3g_opt.cml_task_run_gamess
water_rhf_sto3g_opt.cml_task_track_gamess
```

Task種別は`data_processing`（`training`ではなく）にします。GAMESSの実行は外部プログラムによるデータ処理であり、機械学習のtrainingではないためです。

## Agentコードの更新

`cml_task_run_gamess.py`・`cml_task_track_gamess.py`などAgent上で動くPythonコードを変更する場合は、その差分がAgentへ届く必要があります。

`cml_pipeline_gamess.py`はTaskを作る時点で`repository`・`branch`・commit・未commit差分（`git diff --binary HEAD`）を確定してClearMLへ渡します。AgentはそのcommitをcloneしたうえでTaskの差分を適用します。毎回commitする必要はありませんが、新規ファイルは`git add`してから投入してください。

`examples/`の`.cml.py`は既定で`SOURCE_REPOSITORY="origin"`（`git remote origin`）をclone元にします。別の場所を使う場合は`CLEARML_TASK_REPOSITORY`で上書きしてください。branchは`CLEARML_TASK_BRANCH`、特定commitは`CLEARML_TASK_COMMIT`で指定できます。

WindowsでTaskを作ってmacOS Agentで実行する場合、WindowsのローカルパスはmacOSから見えません。その場合はGitのremote URL・共有ファイルシステム上のパス・macOS側のローカルパスのいずれかを`CLEARML_TASK_REPOSITORY`で明示してください。

## GAMESSバージョンとIntel MPI

**バージョンの自動検出**

`tools/start_clearml_agent.py`でAgentを起動する場合は、GAMESSディレクトリの`gamess.*.x`または`gamess.*.exe`からバージョンを推定し、`CLEARML_GAMESS_VERSION`としてAgentに渡します。別のバージョンを使う場合は`CLEARML_GAMESS_VERSION`または`GAMESS_VERSION`を設定してください。

Windowsの既定は`version="2023.R1.intel"`で、`C:/Users/Public/gamess-64/gamess.2023.R1.intel.exe`を探します。

**Intel MPI（Windows/Linux x86_64）**

このリポジトリのPython環境にWindows/Linux x86_64向けに`impi-devel`を含んでいます。GAMESS実行時に必要なIntel MPI runtimeをPython環境側から供給するためです。`run_gamess.py`は起動時に他現環境の`Library/bin`を`PATH`へ追加し、GAMESSからMPI関連DLLが見えるようにします。

macOS arm64ではpipから`impi-devel`をインストールできないため、requirementsからplatform markerで除外しています。macOSでGAMESSを動かす場合は、Intel MPIを別途用意してください。

## 実装メモ（macOS/Linux）

**readlink -f の互换性**

一部の`rungms`スクリプトはGNU系の`readlink -f`を使います。macOS標準の`readlink`には`-f`がないため、このコードは一時作業ディレクトリに互换shimを作り、`PATH`の先頭に追加してから`rungms`を起動します。

**rungms内のGMSPATH固定値**

`rungms`スクリプト内に`GMSPATH`が固定で書かれている場合は、GAMESSインストール先を直接編集せず、一時作業ディレクトリに`rungms`のコピーを作り、そのコピーの`GMSPATH`だけをTask側で見つけたGAMESSディレクトリへ補正します。

**カレントディレクトリ**

macOS/Linux版の`rungms`は拡張子なしの入力名を受け取り、カレントディレクトリから入力ファイルを読む構成が多いです。そのため、入力ファイルはAgent側の一時作業ディレクトリにコピーし、そこをカレントディレクトリにして`rungms <stem>`を実行します。

## 設計

`cml_task_run_gamess.py`:

- `pipeline_input`を受け取る。ローカルパスで見つからない場合はClearMLに保存された入力ファイルから取得する
- `pipeline_input_patch`がある場合はAgent側で入力ファイルに適用し、最終的に使う入力を作る
- 実際にGAMESSへ渡した入力を`gamess_input`として登録する
- Agent側に、その実行専用の一時ディレクトリを作る
- GAMESSを投入し、起動直後の明らかな失敗だけを確認する
- `cml_task_track_gamess.py`に渡すための`gamess_run_manifest`をアーティファクトとして登録する
- 実際に起動した`rungms`または`rungms.bat`を`gamess_rungms`として登録する

`pipeline_input_patch`は`git diff`や`git diff --no-index`で作れるunified diffを想定しています。Agent側では一時ディレクトリに`pipeline_input`を展開し、`git apply`でpatchを適用します。入力ファイルがこのリポジトリ内にあり変更も同じリポジトリの未commit差分として管理できる場合は、ClearMLのscript diffで運ぶ方法も使えます。別リポジトリやリポジトリ外の入力ファイルにも同じ仕組みを使うなら、`pipeline_input`と`pipeline_input_patch`をartifactとして渡す方が明示的です。

別リポジトリからこのタスク実行コードを使う場合でも、run/track Taskのsource codeとしてClearMLがcloneするのはTask側に設定したリポジトリです。外部リポジトリの入力ファイルは自動でcloneされず、`pipeline_input`アーティファクトとして扱います。

`gamess_run_manifest`はGAMESSの終了結果ではなく、後続の`cml_task_track_gamess.py`が追跡を始めるための実行マニフェストです。フィールド例:

- `schema`: manifestの形式
- `mode`: `submit_only`
- `input_path`: Agent上で実際に使った入力ファイル
- `gamess_dir`、`version`、`ncpus`: 実行環境
- `live_log_path`: `cml_task_track_gamess.py`が追跡するログファイル
- `scratch_dir`、`scratch_pattern`: scratch/restartファイルを回収するための情報
- `rungms_path`: 実際に起動した`rungms`または`rungms.bat`
- `submission_status`: `submitted`、`submit_failed`、`startup_failed`
- `pid`、`submitted_at`: 投入したプロセスの情報

この段階GAMESSの計算はまだ終わっていないため、`gamess_termination`は入れません。`artifact_names`のようなClearML内部の都合を示す値も入れません。

`cml_task_track_gamess.py`:

- `cml_task_run_gamess.py`由来のTaskから`gamess_run_manifest`を取得する
- ログ先頭は初回に全表示し、その後は追記分をテーリングする
- マニフェストに書かれた情報をもとにGAMESSのログを取得する
- submit-onlyモードでは、track側から実ログパスが見えない/読めない場合は即エラーにする（アーティファクトコピーへのフォールバックはしない）
- ログ中の終了メッセージを読み、計算状態を判定する
- 判定結果を`tracking_metrics`に書き出し、アーティファクトとして登録する
- `gamess_log`をテキストプレビュー付きのアーティファクトとして登録する
- 必要なGAMESSログからscratch/restartディレクトリを読み取り、対象ファイルを`gamess_temp`として登録する
- trackループ内でエネルギー抽出などのcallbackを実行する
- GAMESSが失敗していた場合は、アーティファクトを残したうえでClearML Taskをfailedにする

`tracking_metrics`には追跡・判定の結果だけを入れます。基本は`return_code`と`gamess_status`で、`gamess_status`は`completed`、`failed`、`running`、`missing_log`、`unknown`のいずれかです。入力ファイルやログのパス、GAMESSのバージョンなど実行の由来を示す情報は`gamess_run_manifest`に残します。
