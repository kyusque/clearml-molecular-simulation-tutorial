# clearml_gamess

[English version](README.md)

`clearml_gamess/`は、GAMESSの計算をClearML Task/Pipelineで実行・追跡するための再利用コードをまとめたディレクトリです。

- `run_gamess.py`: GAMESSジョブを投入し、実行マニフェストJSONに書き出す
- `track_gamess.py`: GAMESSログを追跡・判定し、抽出値を`tracking_metrics`に書き出す
- `cml_task_run_gamess.py`: Pipelineの`run_gamess`ステップで使うTask定義（ClearML Agent上で実行）
- `cml_task_track_gamess.py`: Pipelineの`track_gamess`ステップで使うTask定義（ClearML Agent上で実行）
- `cml_pipeline_gamess.py`: `run_gamess`ステップと`track_gamess`ステップを持つClearML Pipeline定義
- `examples/`: `.inp`と、それに対応する`<入力ファイル名（拡張子なし）>.cml.py`のClearMLタスク投入例

`build_pipeline()`を呼ぶ前に、`CLEARML_CONFIG_FILE`を設定しておく必要があります。未設定なら即エラーにします。

## Agentで使うコード

`cml_pipeline_gamess.py`は、ClearML Taskの`repository`に既定でこのリポジトリのローカルパスを使います。同じマシン上でPipelineControllerとClearML Agentを動かす開発時は、この形がいちばん素直です。

submit側は、Taskを作る時点で`repository`、`branch`、`commit`、未commit差分を確定してClearMLへ渡します。`repository`はAgentがcloneする場所で、`HEAD`のようなcommit名ではありません。`examples/`の`.cml.py`は既定で`SOURCE_REPOSITORY="origin"`を指定し、`git remote origin`をclone元にします。commitは別に`git rev-parse HEAD`で確定します。別の場所を使う場合は`CLEARML_TASK_REPOSITORY`で上書きしてください。branchは`CLEARML_TASK_BRANCH`、特定commitは`CLEARML_TASK_COMMIT`で指定できます。

WindowsでTaskを作ってmacOS Agentで実行する場合、Windowsの`C:/Users/...`はmacOSから見えません。その場合は、macOS側のローカルリポジトリパス、共有ファイルシステム上のパス、またはGit remoteのどれかを明示する必要があります。`cml_pipeline_gamess.py`は実行に必要なPythonコードの`git diff --binary HEAD`をTaskに渡すため、base commitがAgentからcloneできれば、未commit差分もAgent側で適用されます。新規ファイルは`git add`してから投入してください。

Gitが強く関係するのは、主にAgent上で動くPythonコードを調整する人です。たとえば、アーティファクト登録、ログのプレビュー、scratch回収、metrics抽出、run/track間のJSON受け渡しを直す場合は、その差分がAgentへ届く必要があります。このとき、毎回commitする必要はありません。Agentがcloneできるbase commitがあり、意図した変更がClearML Taskのsource diffに入っていれば、Agent側でその差分が適用されます。新規ファイルだけは`git add`しておかないとdiffに入らないことがあるため注意してください。

一方、GAMESS inputを少し変えて流したいだけの利用者は、Git運用を前面に出す必要はありません。`.inp`と`.cml.py`を編集して新しいPipelineを作り、入力は`pipeline_input`アーティファクトとしてClearMLへ渡す、という考え方で十分です。ClearMLの公式best practiceにある「未commit差分もあとから調べられるように残す」という考えは、ここでは主にタスク実行コードやcallbackを開発している人向けの話として扱います。

## GAMESSのインストール

このリポジトリにはGAMESS本体は含めていません。ClearML Agentが動くマシンに、あらかじめGAMESSをインストールしておく必要があります。

このチュートリアルの動作確認は主にWindowsのGAMESS配布物を想定しています。Windowsでは、GAMESSを`C:/Users/Public/gamess-64`に展開し、その中に`rungms.bat`と`gamess.<version>.exe`がある状態を既定にしています。

macOS/Linuxでは、GAMESSを自分でソースビルドして、`rungms`が使える状態にしてください。このコードではGAMESSのビルド方法そのものは扱いません。Agent側では`rungms`のパスを追跡し、その親ディレクトリをGAMESSディレクトリとして扱います。

`GAMESS_DIR`を明示しない場合、`cml_task_run_gamess.py`がGAMESSの場所を探します。Windowsでは`C:/Users/Public/gamess-64`を使います。macOS/Linuxでは`PATH`上の`rungms`を探し、その親ディレクトリをGAMESSのディレクトリとして扱います。

macOS/Linuxで`rungms`を`PATH`に置かない場合は、Agentを起動する環境で`CLEARML_GAMESS_DIR`または`GAMESS_DIR`を設定してください。`cml_task_run_gamess.py`は、まずこれらの環境変数を見て、その下に`rungms`があるか確認します。

このリポジトリの`tools/start_clearml_agent.py`からAgentを起動する場合は、起動時に`rungms`を探し、見つかったディレクトリを`CLEARML_GAMESS_DIR`としてAgentプロセスへ渡します。`CLEARML_GAMESS_VERSION`が未設定なら、GAMESSディレクトリの`gamess.*.x`または`gamess.*.exe`からversionを推定して渡します。

macOS/Linux版の`rungms`は、拡張子なしの入力名を受け取り、入力ファイルをカレントディレクトリから読む構成があります。そのため、このコードは入力ファイルをGAMESSディレクトリには置かず、Agent側で作った計算ごとの一時作業ディレクトリにコピーし、その一時作業ディレクトリをカレントディレクトリにして`rungms <stem>`を実行します。補助ファイル探索のため、`GMSPATH`と`GAMESS_DIR`にはGAMESSディレクトリを渡します。

GAMESSの`rungms`にはGNU系の`readlink -f`を使う版があります。macOS標準の`readlink`には`-f`がないため、このコードは一時作業ディレクトリに互換shimを作り、PATHの先頭に追加してから`rungms`を起動します。Agent環境に`GMSPATH`が既にある場合でも、Task側で見つけたGAMESSディレクトリを優先します。

`rungms`スクリプト内に`GMSPATH`が固定で書かれている場合は、GAMESSインストール先を直接編集せず、一時作業ディレクトリに`rungms`のコピーを作って、そのコピーの`GMSPATH`だけをtask側で見つけたGAMESSディレクトリへ補正します。

Windowsでは、このディレクトリに少なくとも次のファイルがある前提です。

- `rungms.bat`
- `gamess.<version>.exe`

Windowsの既定設定では`version="2023.R1.intel"`を使うため、`C:/Users/Public/gamess-64/gamess.2023.R1.intel.exe`を探します。macOS/Linuxでは、versionを明示しない場合はGAMESSディレクトリの`gamess.*.x`からversionを推定します。別のバージョンを使う場合は、Agentを起動する環境で`CLEARML_GAMESS_VERSION`または`GAMESS_VERSION`を設定してください。

WindowsとLinux x86_64のPython環境には`impi-devel`を入れています。このコードでは、GAMESS実行時に必要なIntel MPI runtimeをPython環境側の`impi-devel`/`impi-rt`から供給する前提です。`run_gamess.py`は実行時に仮想環境の`Library/bin`を`PATH`へ追加し、GAMESSからMPI関連DLLが見えるようにします。

GAMESS本体のディレクトリだけを別の場所へコピーして実行する場合でも、必要なIntel MPI runtimeが`PATH`から見えるようにしておく必要があります。Windows/Linux x86_64では`impi-devel`を使えますが、macOS arm64ではpipから`impi-devel`をインストールできないため、ClearML Taskのrequirementsからはplatform markerで除外しています。`impi-devel`はGAMESS本体の代替ではありませんが、このチュートリアルのWindows実行ではGAMESSを起動するためのruntime依存として扱っています。

## 設計

`cml_task_run_gamess.py`:

- `pipeline_input`を受け取る。ローカルパスで見つからない場合はClearMLに保存された入力ファイルから取得する
- `pipeline_input_patch`がある場合はAgent側で入力ファイルに適用し、最終的に使う入力を作る
- 実際にGAMESSへ渡した入力を`gamess_input`として登録する
- Agent側に、その実行専用の一時ディレクトリを作る
- GAMESSを投入し、起動直後の明らかな失敗だけを確認する
- `cml_task_track_gamess.py`に渡すための`gamess_run_manifest`をアーティファクトとして登録する
- 実際に起動した`rungms`または`rungms.bat`を`gamess_rungms`として登録する

`pipeline_input_patch`は`git diff`や`git diff --no-index`で作れるunified diffを想定しています。Agent側では一時ディレクトリに`pipeline_input`を展開し、`git apply`でpatchを適用します。入力ファイルがこのリポジトリ内にあり、変更も同じリポジトリの未commit差分として管理できる場合は、ClearMLのscript diffで運ぶ方法も使えます。ただし、別リポジトリやリポジトリ外の入力ファイルにも同じ仕組みを使うなら、`pipeline_input`と`pipeline_input_patch`をartifactとして渡す方が明示的です。

別リポジトリからこのタスク実行コードを使う場合でも、run/track Taskのsource codeとしてClearMLがcloneするのはTask側に設定したリポジトリです。外部リポジトリの入力ファイルは自動でcloneされず、`pipeline_input`アーティファクトとして扱います。

submit-onlyモードの`gamess_run_manifest`は、GAMESSの終了結果ではなく、後続の`cml_task_track_gamess.py`が追跡を始めるための実行マニフェストです。たとえば以下のような値を入れます。

- `schema`: manifestの形式
- `mode`: `submit_only`
- `input_path`: Agent上で実際に使った入力ファイル
- `gamess_dir`、`version`、`ncpus`: 実行環境
- `live_log_path`: `cml_task_track_gamess.py`が追跡するログファイル
- `scratch_dir`、`scratch_pattern`: scratch/restartファイルを回収するための情報
- `rungms_path`: 実際に起動した`rungms`または`rungms.bat`
- `submission_status`: `submitted`、`submit_failed`、`startup_failed`
- `pid`、`submitted_at`: 投入したプロセスの情報

この段階ではGAMESSの計算がまだ終わっていないため、`gamess_termination`は入れません。`artifact_names`のようなClearML内部の都合を示す値も入れません。

`cml_task_track_gamess.py`:

- `cml_task_run_gamess.py`由来のTaskから`gamess_run_manifest`を取得する
- ログ先頭は初回に全表示し、その後は追記分をテーリングする
- マニフェストに書かれた情報をもとにGAMESSのログを取得する
- submit-onlyモードでは、track側から実ログパスが見えない/読めない場合は即エラーにする（アーティファクトコピーへのフォールバックはしない）
- ログ中の終了メッセージを読み、計算状態を判定する
- 判定結果を`tracking_metrics`に書き出し、アーティファクトとして登録する
- `gamess_log`をテキストプレビュー付きのアーティファクトとして登録する
- 必要ならGAMESSログからscratch/restartディレクトリを読み取り、対象ファイルを`gamess_temp`として登録する
- trackループ内でエネルギー抽出などのcallbackを実行する
- GAMESSが失敗していた場合は、アーティファクトを残したうえでClearML Taskをfailedにする

Pipeline Taskに集約する監視アーティファクトは、Taskごとに名前を分けます（例: `pipeline_input`, `pipeline_input_patch`, `run_gamess_input`, `run_gamess_manifest`, `run_gamess_rungms`, `track_gamess_metrics`, `track_gamess_log`, `track_gamess_temp`）。

終了判定メッセージ:

- `EXECUTION OF GAMESS TERMINATED NORMALLY`: 正常終了
- `EXECUTION OF GAMESS TERMINATED -ABNORMALLY-`: 異常終了

`tracking_metrics`には、追跡・判定の結果だけを入れます。基本は`return_code`と`gamess_status`です。`gamess_status`は`completed`、`failed`、`running`、`missing_log`、`unknown`のいずれかにします。入力ファイルやログのパス、GAMESSのバージョンなど、実行の由来を示す情報は`gamess_run_manifest`に残します。

## 命名

ClearML UIでは長いTask名が省略されるため、入力ファイル名（拡張子なし）を先頭に置きます。

- `<入力ファイル名（拡張子なし）>.cml_pipeline_gamess`
- `<入力ファイル名（拡張子なし）>.cml_task_run_gamess`
- `<入力ファイル名（拡張子なし）>.cml_task_track_gamess`

例:

```text
success_fast_water.cml_task_run_gamess
success_fast_water.cml_task_track_gamess
```

ClearMLのTask種別は`training`ではなく`data_processing`にします。GAMESSの実行は機械学習のtrainingではなく、外部プログラムによるデータ処理に近いためです。

## examples

```text
examples/
  gamess_test_cases/
    success_fast_water.inp
    success_fast_water.cml.py
```

`.cml.py`は、ユーザーが編集するClearMLタスク投入用スクリプトです。ここには、プロジェクト名、キュー、GAMESS入力、必要ならGAMESSのインストール先、バージョン、CPU数のような実行条件だけを書きます。

ログ、実行マニフェストJSON、metrics JSON、scratch/tempディレクトリなどの生成物のパスは、ユーザーが直接書きません。キュー投入後にAgentが実行する`cml_task_run_gamess.py`と`cml_task_track_gamess.py`が、実行ごとに一時ディレクトリを作って管理します。
