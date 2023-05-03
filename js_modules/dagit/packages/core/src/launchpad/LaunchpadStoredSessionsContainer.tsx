import * as React from 'react';

import {
  applyChangesToSession,
  applyCreateSession,
  IExecutionSessionChanges,
  useExecutionSessionStorage,
  useInitialDataForMode,
} from '../app/ExecutionSessionStorage';
import {RepoAddress} from '../workspace/types';

import {LaunchpadType} from './LaunchpadRoot';
import LaunchpadSession from './LaunchpadSession';
import {LaunchpadTabs} from './LaunchpadTabs';
import {
  LaunchpadSessionPartitionSetsFragment,
  LaunchpadSessionPipelineFragment,
} from './types/LaunchpadRoot.types';

interface Props {
  launchpadType: LaunchpadType;
  pipeline: LaunchpadSessionPipelineFragment;
  partitionSets: LaunchpadSessionPartitionSetsFragment;
  repoAddress: RepoAddress;
  rootDefaultYaml: string | undefined;
}

export const LaunchpadStoredSessionsContainer = (props: Props) => {
  const {launchpadType, pipeline, partitionSets, repoAddress, rootDefaultYaml} = props;

  const initialDataForMode = useInitialDataForMode(pipeline, partitionSets, rootDefaultYaml);
  const [data, onSave] = useExecutionSessionStorage(repoAddress, pipeline.name, initialDataForMode);

  const onCreateSession = () => {
    onSave(applyCreateSession(data, initialDataForMode));
  };

  const onSaveSession = (changes: IExecutionSessionChanges) => {
    onSave(applyChangesToSession(data, data.current, changes));
  };

  const currentSession = data.sessions[data.current];

  return (
    <>
      <LaunchpadTabs data={data} onCreate={onCreateSession} onSave={onSave} />
      <LaunchpadSession
        launchpadType={launchpadType}
        session={currentSession}
        onSave={onSaveSession}
        pipeline={pipeline}
        partitionSets={partitionSets}
        repoAddress={repoAddress}
      />
    </>
  );
};

// eslint-disable-next-line import/no-default-export
export default LaunchpadStoredSessionsContainer;
