import ollama

def pull_model(model: str):
	try:
		ollama.show(model)
	except ollama.ResponseError:
		try:
			import sys
			from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

			current_digest = ""
			tasks = {}

			with Progress(
				TextColumn("[bold blue]{task.description}"),
				BarColumn(),
				DownloadColumn(),
				TransferSpeedColumn(),
				TimeRemainingColumn(),
			) as progress:
				for item in ollama.pull(model, stream=True):
					digest = item.get("digest", "")

					if digest != current_digest and current_digest in tasks:
						progress.stop_task(tasks[current_digest])

					if not digest:
						print(item.get("status"))
						continue

					if digest not in tasks and (total := item.get("total")):
						tasks[digest] = progress.add_task(
							f"pulling {digest[7:19]}",
							total=total,
						)

					if completed := item.get("completed"):
						progress.update(tasks[digest], completed=completed)

					current_digest = digest

		except KeyboardInterrupt:
			sys.exit(0)