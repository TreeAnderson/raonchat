-- raonChat: Supabase pgvector 설정
-- Supabase SQL Editor에서 실행하세요.

-- 1. pgvector 확장 활성화
create extension if not exists vector;

-- 2. 기존 테이블/함수 삭제 (재실행 시)
drop function if exists match_documents;
drop table if exists documents;

-- 3. documents 테이블 생성 (gemini-embedding-001: 3072차원)
create table documents (
    id uuid primary key default gen_random_uuid(),
    content text not null,
    embedding vector(3072),
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

-- 4. match_documents RPC 함수 (cosine similarity 검색)
-- 참고: gemini-embedding-001은 3072차원으로 IVFFlat(최대 2000차원) 사용 불가.
-- 문서 수가 수천 개 이하이면 인덱스 없이 sequential scan으로 충분.
create or replace function match_documents(
    query_embedding vector(3072),
    match_count int default 3,
    filter jsonb default '{}'::jsonb
)
returns table (
    id uuid,
    content text,
    metadata jsonb,
    similarity float
)
language plpgsql
as $$
begin
    return query
    select
        d.id,
        d.content,
        d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    from documents d
    where case
        when filter = '{}'::jsonb then true
        else d.metadata @> filter
    end
    order by d.embedding <=> query_embedding
    limit match_count;
end;
$$;

-- 5. chat_logs 테이블 (사용자 대화 로그)
drop table if exists chat_logs;

create table chat_logs (
    id uuid primary key default gen_random_uuid(),
    query text not null,
    response text not null,
    source_documents jsonb default '[]'::jsonb,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

-- 6. RLS 비활성화 & anon 권한 부여
alter table documents disable row level security;
alter table chat_logs disable row level security;
grant all on documents to anon;
grant all on chat_logs to anon;
