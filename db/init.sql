CREATE TYPE public."StepType" AS ENUM (
    'assistant_message',
    'embedding',
    'llm',
    'retrieval',
    'rerank',
    'run',
    'system_message',
    'tool',
    'undefined',
    'user_message'
);
ALTER TYPE public."StepType" OWNER TO chainlit;
CREATE TABLE public."Element" (
    id text DEFAULT gen_random_uuid() NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "threadId" text,
    "stepId" text NOT NULL,
    metadata jsonb NOT NULL,
    mime text,
    name text NOT NULL,
    "objectKey" text,
    url text,
    "chainlitKey" text,
    display text,
    size text,
    language text,
    page integer,
    props jsonb
);
ALTER TABLE public."Element" OWNER TO chainlit;
CREATE TABLE public."Feedback" (
    id text DEFAULT gen_random_uuid() NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "stepId" text,
    name text NOT NULL,
    value double precision NOT NULL,
    comment text
);
ALTER TABLE public."Feedback" OWNER TO chainlit;
CREATE TABLE public."Step" (
    id text DEFAULT gen_random_uuid() NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "parentId" text,
    "threadId" text,
    input text,
    metadata jsonb NOT NULL,
    name text,
    output text,
    type public."StepType" NOT NULL,
    "showInput" text DEFAULT 'json'::text,
    "isError" boolean DEFAULT false,
    "startTime" timestamp(3) without time zone NOT NULL,
    "endTime" timestamp(3) without time zone NOT NULL
);
ALTER TABLE public."Step" OWNER TO chainlit;
CREATE TABLE public."Thread" (
    id text DEFAULT gen_random_uuid() NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "deletedAt" timestamp(3) without time zone,
    name text,
    metadata jsonb NOT NULL,
    "userId" text,
    tags text [] DEFAULT ARRAY []::text []
);
ALTER TABLE public."Thread" OWNER TO chainlit;
CREATE TABLE public."User" (
    id text DEFAULT gen_random_uuid() NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    metadata jsonb NOT NULL,
    identifier text NOT NULL
);
ALTER TABLE public."User" OWNER TO chainlit;
CREATE TABLE public._prisma_migrations (
    id character varying(36) NOT NULL,
    checksum character varying(64) NOT NULL,
    finished_at timestamp with time zone,
    migration_name character varying(255) NOT NULL,
    logs text,
    rolled_back_at timestamp with time zone,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    applied_steps_count integer DEFAULT 0 NOT NULL
);
ALTER TABLE public._prisma_migrations OWNER TO chainlit;
CREATE TABLE public.checkpoint_blobs (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    channel text NOT NULL,
    version text NOT NULL,
    type text NOT NULL,
    blob bytea
);
ALTER TABLE public.checkpoint_blobs OWNER TO chainlit;
CREATE TABLE public.checkpoint_migrations (v integer NOT NULL);
ALTER TABLE public.checkpoint_migrations OWNER TO chainlit;
CREATE TABLE public.checkpoint_writes (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    checkpoint_id text NOT NULL,
    task_id text NOT NULL,
    idx integer NOT NULL,
    channel text NOT NULL,
    type text,
    blob bytea NOT NULL,
    task_path text DEFAULT ''::text NOT NULL
);
ALTER TABLE public.checkpoint_writes OWNER TO chainlit;
CREATE TABLE public.checkpoints (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    checkpoint_id text NOT NULL,
    parent_checkpoint_id text,
    type text,
    checkpoint jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);
ALTER TABLE public.checkpoints OWNER TO chainlit;
ALTER TABLE ONLY public."Element"
ADD CONSTRAINT "Element_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Feedback"
ADD CONSTRAINT "Feedback_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Step"
ADD CONSTRAINT "Step_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."Thread"
ADD CONSTRAINT "Thread_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public."User"
ADD CONSTRAINT "User_pkey" PRIMARY KEY (id);
ALTER TABLE ONLY public._prisma_migrations
ADD CONSTRAINT _prisma_migrations_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.checkpoint_blobs
ADD CONSTRAINT checkpoint_blobs_pkey PRIMARY KEY (thread_id, checkpoint_ns, channel, version);
ALTER TABLE ONLY public.checkpoint_migrations
ADD CONSTRAINT checkpoint_migrations_pkey PRIMARY KEY (v);
ALTER TABLE ONLY public.checkpoint_writes
ADD CONSTRAINT checkpoint_writes_pkey PRIMARY KEY (
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        task_id,
        idx
    );
ALTER TABLE ONLY public.checkpoints
ADD CONSTRAINT checkpoints_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id);
CREATE INDEX "Element_stepId_idx" ON public."Element" USING btree ("stepId");
CREATE INDEX "Element_threadId_idx" ON public."Element" USING btree ("threadId");
CREATE INDEX "Feedback_createdAt_idx" ON public."Feedback" USING btree ("createdAt");
CREATE INDEX "Feedback_name_idx" ON public."Feedback" USING btree (name);
CREATE INDEX "Feedback_name_value_idx" ON public."Feedback" USING btree (name, value);
CREATE INDEX "Feedback_stepId_idx" ON public."Feedback" USING btree ("stepId");
CREATE INDEX "Feedback_value_idx" ON public."Feedback" USING btree (value);
CREATE INDEX "Step_createdAt_idx" ON public."Step" USING btree ("createdAt");
CREATE INDEX "Step_endTime_idx" ON public."Step" USING btree ("endTime");
CREATE INDEX "Step_name_idx" ON public."Step" USING btree (name);
CREATE INDEX "Step_parentId_idx" ON public."Step" USING btree ("parentId");
CREATE INDEX "Step_startTime_idx" ON public."Step" USING btree ("startTime");
CREATE INDEX "Step_threadId_idx" ON public."Step" USING btree ("threadId");
CREATE INDEX "Step_threadId_startTime_endTime_idx" ON public."Step" USING btree ("threadId", "startTime", "endTime");
CREATE INDEX "Step_type_idx" ON public."Step" USING btree (type);
CREATE INDEX "Thread_createdAt_idx" ON public."Thread" USING btree ("createdAt");
CREATE INDEX "Thread_name_idx" ON public."Thread" USING btree (name);
CREATE INDEX "User_identifier_idx" ON public."User" USING btree (identifier);
CREATE UNIQUE INDEX "User_identifier_key" ON public."User" USING btree (identifier);
CREATE INDEX checkpoint_blobs_thread_id_idx ON public.checkpoint_blobs USING btree (thread_id);
CREATE INDEX checkpoint_writes_thread_id_idx ON public.checkpoint_writes USING btree (thread_id);
CREATE INDEX checkpoints_thread_id_idx ON public.checkpoints USING btree (thread_id);
ALTER TABLE ONLY public."Element"
ADD CONSTRAINT "Element_stepId_fkey" FOREIGN KEY ("stepId") REFERENCES public."Step"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Element"
ADD CONSTRAINT "Element_threadId_fkey" FOREIGN KEY ("threadId") REFERENCES public."Thread"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Feedback"
ADD CONSTRAINT "Feedback_stepId_fkey" FOREIGN KEY ("stepId") REFERENCES public."Step"(id) ON UPDATE CASCADE ON DELETE
SET NULL;
ALTER TABLE ONLY public."Step"
ADD CONSTRAINT "Step_parentId_fkey" FOREIGN KEY ("parentId") REFERENCES public."Step"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Step"
ADD CONSTRAINT "Step_threadId_fkey" FOREIGN KEY ("threadId") REFERENCES public."Thread"(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public."Thread"
ADD CONSTRAINT "Thread_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE
SET NULL;