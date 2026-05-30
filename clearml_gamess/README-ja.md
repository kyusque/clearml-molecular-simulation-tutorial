# clearml_gamess

[English version](README.md)

`clearml_gamess/`は、GAMESSの計算をClearML Task/Pipelineで実行・追跡するための再利用コードをまとめたディレクトリです。

- `run_gamess.py`: GAMESSジョブをsubmitし、実行マニフェストJSONに書き出す
- `track_gamess.py`: GAMESSログを追跡・判定し、抽出値を`tracking_metrics`に書き出す
- `cml_task_run_gamess.py`: Pipelineの`run_gamess`ステップで使うTask定義（ClearML Agent上で実行）
- `cml_task_track_gamess.py`: Pipelineの`track_gamess`ステップで使うTask定義（ClearML Agent上で実行）
- `cml_pipeline_gamess.py`: `run_gamess`ステップと`track_gamess`ステップを持つClearML Pipeline定義
- `examples/`: `.inp`と、それに対応する`<入力ファイル名（拡張子なし）>.cml.py`の投入例

`build_pipeline()`を呼ぶ前に、`CLEARML_CONFIG_FILE`を設定しておく必要があります。未設定なら即エラーにします。

## 設計

`cml_task_run_gamess.py`:

- `gamess_input`を受け取る。ローカルパスで見つからない場合はアーティファクトから取得する
- Agent側に、その実行専用の一時ディレクトリを作る
- GAMESSを投入し、起動直後の明らかな失敗だけを確認する
- `cml_task_track_gamess.py`に渡すための`gamess_run_manifest`をアーティファクトとして登録する

submit-onlyモードの`gamess_run_manifest`は、GAMESSの終了結果ではなく、後続の`cml_task_track_gamess.py`が追跡を始めるための情報です。たとえば以下のような値を入れます。

- `schema`: manifestの形式
- `mode`: `submit_only`
- `input_path`: Agent上で実際に使った入力ファイル
- `gamess_dir`、`version`、`ncpus`: 実行環境
- `live_log_path`: `cml_task_track_gamess.py`が追跡するログファイル
- `scratch_dir`、`scratch_pattern`: scratch/restartファイルを回収するための情報
- `submission_status`: `submitted`、`submit_failed`、`startup_failed`
- `pid`、`submitted_at`: 投入したプロセスの情報

この段階ではGAMESSの計算がまだ終わっていないため、`gamess_termination`は入れません。`artifact_names`のようなClearML内部の都合を示す値も入れません。

`cml_task_track_gamess.py`:

- `cml_task_run_gamess.py`由来のTaskから`gamess_run_manifest`を取得する
- ログ先頭は初回に全表示し、その後は追記分をテーリングする
- マニフェストに書かれた情報をもとにGAMESSのログを取得する
- submit-onlyモードでは、track側から実ログパスが見えない/読めない場合は即エラーにする（artifactコピーへのフォールバックはしない）
- ログ中の終了メッセージを読み、計算状態を判定する
- 判定結果を`tracking_metrics`に書き出し、アーティファクトとして登録する
- `gamess_log`をテキストプレビュー付きのアーティファクトとして登録する
- 必要ならscratch/restartファイルを`gamess_temp`として登録する
- エネルギー抽出など、追加の後処理コールバックを実行する
- GAMESSが失敗していた場合は、アーティファクトを残したうえでClearML Taskをfailedにする

Pipeline Taskに集約する監視artifactは、taskごとに名前を分けます（例: `pipeline_gamess_input`, `run_gamess_manifest`, `track_gamess_metrics`, `track_gamess_log`, `track_gamess_temp`）。

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

`.cml.py`は、ユーザーが編集する投入用スクリプトです。ここには、プロジェクト名、キュー、GAMESS入力、GAMESSのインストール先、バージョン、CPU数のような実行条件だけを書きます。

ログ、実行マニフェストJSON、metrics JSON、scratch/tempディレクトリなどの生成物のパスは、ユーザーが直接書きません。キュー投入後にAgentが実行する`cml_task_run_gamess.py`と`cml_task_track_gamess.py`が、実行ごとに一時ディレクトリを作って管理します。
