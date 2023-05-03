import * as React from 'react';

import {
  createSingleSession,
  IExecutionSession,
  IExecutionSessionChanges,
  useInitialDataForMode,
} from '../app/ExecutionSessionStorage';
import {RepoAddress} from '../workspace/types';

import {LaunchpadType} from './LaunchpadRoot';
import LaunchpadSession from './LaunchpadSession';
import {
  LaunchpadSessionPartitionSetsFragment,
  LaunchpadSessionPipelineFragment,
} from './types/LaunchpadRoot.types';

interface Props {
  launchpadType: LaunchpadType;
  pipeline: LaunchpadSessionPipelineFragment;
  partitionSets: LaunchpadSessionPartitionSetsFragment;
  repoAddress: RepoAddress;
  sessionPresets: Partial<IExecutionSession>;
  rootDefaultYaml: string | undefined;
}

export const LaunchpadTransientSessionContainer = (props: Props) => {
  const {
    launchpadType,
    pipeline,
    partitionSets,
    repoAddress,
    sessionPresets,
    rootDefaultYaml,
  } = props;

  const initialData = useInitialDataForMode(pipeline, partitionSets, rootDefaultYaml);
  const initialSessionComplete = createSingleSession({
    ...sessionPresets,
    runConfigYaml: initialData.runConfigYaml,
  });

  const [session, setSession] = React.useState<IExecutionSession>(initialSessionComplete);

  const onSaveSession = (changes: IExecutionSessionChanges) => {
    const newSession = {...session, ...changes};
    setSession(newSession);
  };

  return (
    <LaunchpadSession
      launchpadType={launchpadType}
      session={session}
      onSave={onSaveSession}
      pipeline={pipeline}
      partitionSets={partitionSets}
      repoAddress={repoAddress}
    />
  );
};
