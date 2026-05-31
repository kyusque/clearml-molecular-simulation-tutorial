# ClearML分子シミュレーションチュートリアル

[English version](README.md)

GAMESSなどの分子シミュレーションを実行するとき、こんなことはないでしょうか。

- 計算がいつ終わったかすぐに確認できない
- 過去の計算の入力ファイルやログがどこにあったか分からなくなる
- 複数の計算の結果をまとめて比較したい
- LLMエージェントに計算サイクル全体（ジョブ投入・入出力管理・データセット管理）を任せたいが、それらのAPIを一通り備えた既存ツールがない

このチュートリアルでは、**ClearML**を使ってこれらを解決する方法を示します。ClearMLはジョブ投入・入出力管理・データセット管理のAPIを一つのプラットフォームにまとめて備えており、人間が手作業するワークフローでも、LLMエージェントが自動化するワークフローでも、同じAPIで扱えます。ClearMLに計算を投入すると、入力ファイル・ログ・エネルギーなどの結果が自動的に記録され、WebブラウザやAPIからいつでも確認できるようになります。

## クイックスタート

### 必要なもの

- **ClearMLアカウント** — [app.clear.ml](https://app.clear.ml/)で無料作成できます（[self-host](https://github.com/clearml/clearml-server)も可）
- **GAMESSがインストールされたWindows PC** — GAMESSの設定は[clearml_gamess/README-ja.md](clearml_gamess/README-ja.md)を参照してください
- **uv** — Pythonの依存関係を管理するツールです（手順4でインストールします）

### 手順

#### 1. ClearMLのAPI credentialを取得する

[app.clear.ml](https://app.clear.ml/)にサインアップし、**Settings → Workspace → Create new credentials**からAPI credentialを発行します。

#### 2. このリポジトリをcloneする

```bash
git clone https://github.com/kyusque/clearml-molecular-simulation-tutorial.git
cd clearml-molecular-simulation-tutorial
```

#### 3. 認証情報を設定する

`local/clearml.conf.example`をコピーして`local/clearml.conf`を作り、手順1で発行したAPI credentialを設定します。

#### 4. uvをインストールする

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS/Linuxでは次の形です。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 5. ClearML Agentを起動する

ClearML Agentは、ClearMLから計算ジョブを受け取ってGAMESSを実行するプロセスです。

```powershell
uv run tools/start_clearml_agent.py --queue default --create-queue --cpu-only
```

#### 6. サンプル計算を投入する

別のターミナルで実行します。

```powershell
uv run clearml_gamess/examples/water_rhf_sto3g_opt.cml.py
```

[app.clear.ml](https://app.clear.ml/)を開くと、計算がTaskとして登録され、Agentが実行を始めます。完了後はログ・エネルギーmetricsをWebから確認できます。

## 仕組み

ClearMLを使うと3つの部品が連携して動きます。

| 部品 | 何をするか |
| --- | --- |
| **このPC（投入側）** | `.cml.py`スクリプトを実行して計算をClearMLに登録し、queueに投入する |
| **ClearML Agent** | queueを監視して計算を受け取り、GAMESSを実行する |
| **ClearML Server（app.clear.ml）** | Task・ログ・アーティファクトを管理し、WebブラウザからアクセスできるUIを提供する |

投入から完了までの流れはこうです。

1. `.cml.py`を実行 → 入力ファイルがClearMLに保存され、計算Taskがqueueに入る
2. AgentがTaskを受け取る → GAMESSを実行してログをリアルタイムに送信する
3. 計算が終わる → ログ・エネルギーなどの値・scratch/tempファイルがアーティファクトとして保存される
4. 計算が異常終了した場合 → TaskがfailedになりWebから確認できる

小さく試す場合はすべて同じPCで動かせます。計算を別のマシンに任せたい場合は、そのマシンでAgentを起動します。ClearML Serverはapp.clear.mlのSaaSのほか、自前でself-hostすることもできます。

## 自分の計算を投入する

各入力ファイルのそばに`.cml.py`という投入用スクリプトを置くのがこのリポジトリの規則です。

```
clearml_gamess/examples/
  water_rhf_sto3g_opt.inp        ← GAMESS入力ファイル
  water_rhf_sto3g_opt.cml.py     ← ClearMLへの投入スクリプト
```

自分の計算を投入するには：

1. GAMESS入力ファイル（`.inp`）を用意する
2. 既存の`.cml.py`をコピーしてプロジェクト名・入力ファイルのパスを書き換える
3. `uv run your_calculation.cml.py`で投入する

入力ファイルを変えて再投入するだけであればGitは不要です。ログ解析やmetricsの抽出コードを変える場合は、その変更がAgentへ届く必要があります。新規ファイルは`git add`してから投入してください。

## テストケース

`clearml_gamess/examples/gamess_test_cases/`に動作確認用の入力があります。

| ファイル | 内容 |
| --- | --- |
| `success_fast_water` | 小さい水分子の計算（すぐ終わる） |
| `success_long_c4h6_uhf_hessian` | C4H6のHessian計算（時間がかかる） |
| `error_fast_bad_scf` | SCF収束失敗（失敗Taskの確認用） |
| `error_delayed_timlim_c28` | 時間制限超過（TIMLIMエラーの確認用） |

## 詳細

- GAMESS固有の設定（インストール場所・`rungms`の設定）: [clearml_gamess/README-ja.md](clearml_gamess/README-ja.md)
- Agent・Pipeline・アーティファクトの設計メモ: [skills/clearml/](skills/clearml/)
