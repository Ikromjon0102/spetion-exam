import markRed from "../../assets/logos/spetion-mark-red.png";
import markWhite from "../../assets/logos/spetion-mark-white.png";
import horizontalRed from "../../assets/logos/spetion-lockup-horizontal-red.png";
import horizontalWhite from "../../assets/logos/spetion-lockup-horizontal-white.png";
import stackedRed from "../../assets/logos/spetion-lockup-stacked-red.png";
import stackedWhite from "../../assets/logos/spetion-lockup-stacked-white.png";

const SOURCES = {
  mark: { red: markRed, white: markWhite },
  horizontal: { red: horizontalRed, white: horizontalWhite },
  stacked: { red: stackedRed, white: stackedWhite },
};

interface Props {
  variant?: "mark" | "horizontal" | "stacked";
  tone?: "red" | "white";
  height?: number;
}

export default function Logo({ variant = "horizontal", tone = "red", height = 28 }: Props) {
  return (
    <img
      src={SOURCES[variant][tone]}
      alt="Spetion"
      height={height}
      style={{ height, width: "auto", display: "block" }}
    />
  );
}
