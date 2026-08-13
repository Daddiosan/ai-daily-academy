# AI Daily Academy

24週間（168日）のAI学習カリキュラムを、毎朝クラウドで自動生成してMP3化するプロジェクトです。

## 自動化内容
- 毎朝 06:00 JST に GitHub Actions 起動
- 24週間カリキュラムから次のテーマを選択
- OpenAI Responses API + Web Search で当日のAI最新情報を一次情報中心に収集
- 約30分の日本語音声教材を生成
- OpenAI TTS でMP3化
- GitHub Actions Artifactとして30日間ダウンロード可能
- 通常の自動実行では progress.json と教材本文をリポジトリに保存

## 必須Secret
Settings → Secrets and variables → Actions → New repository secret

Name:
OPENAI_API_KEY

Value:
OpenAI Platformで発行したAPIキー

## 最初のテスト
Actions → AI Daily Academy → Run workflow

day に 1 を入力して実行します。
dayを指定した手動実行では進捗は更新しません。
空欄で実行すると次の日を生成し、進捗を1日進めます。

## 出力
Actions実行画面下部のArtifactsからZIPをダウンロードできます。
中には教材TXT、メタデータJSON、MP3が入ります。

## iPhone / iCloud Drive
次のフェーズで、iPhoneショートカットから最新MP3をiCloud Driveの
AI Daily Academy フォルダへ自動保存する仕組みを追加します。

## 音声
音声はAI生成音声です。教材本文の冒頭でもその旨を明示するよう生成指示しています。
