from pancake import ProgressBar


def test_progressbar_zero_total(capsys):
    pb = ProgressBar(total=0, width=10, prefix='Progress:', suffix='Done', decimals=1)
    pb.update()
    captured = capsys.readouterr().out
    assert '100.0%' in captured
    assert '0/0' in captured

