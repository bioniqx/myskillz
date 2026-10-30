import React from "react";
import { Composition } from "remotion";
import { CARD_LIST } from "../cards/registry";
import { cardFps, cardSize, defaultsOf } from "../cards/types";
import { zodFromCard } from "./zodFromCard";
import { MainComposition } from "../preview/Composition";
import { demoProject } from "../demoProject";
import { projectDuration, projectEndFrame } from "../types";
import type { ProjectData } from "../types";
import { MANIFEST, ORIGINAL } from "../cards/projectCards";
import { buildProjectFromManifest } from "../projectImport";

type MainProps = { project: ProjectData; renderExact?: boolean };
const Main = MainComposition as React.ComponentType<MainProps>;

/** Remotion Studio / CLI entrypoint:
 *  - Main: full timeline composition
 *  - ProjImported: linked film project imported from manifest
 *  - ProjOriginal: film project original composition (parity comparison)
 *    both should match frame-by-frame; scripts/parity.mjs uses them for verification
 *  - Each card is registered as a composition with Zod schema */
export const RemotionRoot: React.FC = () => {
  const demo = demoProject();
  return (
    <>
      <Composition
        id="Main"
        component={Main}
        durationInFrames={projectDuration(demo)}
        fps={demo.fps}
        width={demo.width}
        height={demo.height}
        defaultProps={{ project: demo, renderExact: false }}
        calculateMetadata={({ props }) => ({
          // Export (renderExact) uses exact content duration; Studio preview includes 1s padding
          durationInFrames: props.renderExact
            ? Math.max(2, projectEndFrame(props.project))
            : projectDuration(props.project),
          fps: props.project.fps,
          width: props.project.width,
          height: props.project.height,
        })}
      />
      {MANIFEST && (
        <Composition
 *  - ProjImported: linked film project imported from manifest
          component={Main}
          durationInFrames={Math.max(2, MANIFEST.total)}
          fps={MANIFEST.fps}
          width={MANIFEST.width}
          height={MANIFEST.height}
          defaultProps={{ project: buildProjectFromManifest(MANIFEST), renderExact: true }}
        />
      )}
      {MANIFEST && ORIGINAL && (
        <Composition
 *  - ProjOriginal: film project original composition (parity comparison)
          component={ORIGINAL}
          durationInFrames={Math.max(2, MANIFEST.total)}
          fps={MANIFEST.fps}
          width={MANIFEST.width}
          height={MANIFEST.height}
        />
      )}
      {CARD_LIST.filter((c) => c.kind !== "audio").map((card) => {
        const { width, height } = cardSize(card);
        return (
          <Composition
            key={card.id}
            id={card.id.replace(/[^a-zA-Z0-9-]/g, "-")}
            // Dynamic registration: runtime schema validation with Zod
            component={card.component as React.ComponentType<Record<string, unknown>>}
            durationInFrames={Math.max(2, card.durationInFrames)}
            fps={cardFps(card)}
            width={width}
            height={height}
            schema={zodFromCard(card) as never}
            defaultProps={defaultsOf(card) as never}
          />
        );
      })}
    </>
  );
};
