/** External video project source (workbench/proj symlink -> <project>/src, alias @proj).
 *  Declared as any module: external project is not subject to workbench tsc checking. */
declare module "@proj/*";

/** Shot card demo source (workbench/demosrc -> ../demos, alias @demos).
 *  Not subject to local strict checking: demo source checked by repo CI tsc. */
declare module "@demos/*";
